"""
generalization.py
=============================
Generalization layer (build spec section 6): recombined-chunk items (three types, Q10), mixed items
(2 trained + 2 new chunks) and new-chunk items.

  musical-only  trained musical chunks in a new order; crossing motor chunks break
  motor-only    trained misaligned motor chunks in a new order; the musical chunks are new
  both          every musical and every misaligned motor chunk is trained (junction pairs recur)

The type of a recombined item is derived from the trained proportions (family/trained.py), not assumed.

What each builder does (all called by selection/assemble.assemble_family, once per set):
  recombined_musical  permutations of the set's trained chunks that are not a base order, fingered with the set's
                      fingering pinned; keeps the first 'both' and the first 'musical-only'
  recombined_motor    chains the bases' misaligned motor-chunk pieces (as played) into a new 12-note item, depth-first,
                      with pruning; keeps the result with the most new musical chunks
  mixed_or_new        a chunk order from the whole inventory with exactly n_trained trained chunks (2 = mixed item,
                      0 = new-chunk item); the new chunks are registered with the first neutral fingering found
New chunks get registry IDs 'new:<pitches>' (register_new).
"""

import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import versions as vs
from ukustim.core.fingering import positions_of, valid_assignments
from ukustim.core.inventory import Inventory
from ukustim.core.items import ChunkDef, Item, Registry, build_item, is_trained_id, item_from_positions
from ukustim.family.trained import Trained

Chunk = Tuple[int, ...]


def register_new(reg: Registry, pitches: Chunk, fingering: Sequence[fb.Pos]) -> str:
    """Registry entry for a chunk outside the trained inventory; same pitches with another fingering get a suffix.
    Returns the ID: 'new:G4-F4-E4' the first time, 'new:G4-F4-E4~2' if those pitches come back with another
    fingering (one ID = one fingering, as for trained chunks). An existing identical entry is reused."""
    base_id = "new:" + ch.chunk_id(pitches)
    cid, k = base_id, 1
    # walk through base_id, base_id~2, ... until the ID is free or already holds exactly this fingering
    while cid in reg and reg[cid].fingering != tuple(fingering):
        k += 1
        cid = f"{base_id}~{k}"
    reg.setdefault(cid, ChunkDef(cid, tuple(pitches), tuple(fingering), None, "new"))
    return cid


# ---------------------------------------------------------------------------
# Recombined, musical chunks reordered: musical-only or both
# ---------------------------------------------------------------------------

def recombined_musical(inv: Inventory, bases: Sequence[Item], trained_chunks: Sequence[Chunk],
                       fingering: Dict[Chunk, int], comps, reg: Registry, rng: random.Random
                       ) -> Dict[str, Item]:
    """Trained chunks in an order no base uses. Returns {'both': item, 'musical-only': item} (those found).

    Every chunk is trained by construction (prop_trained_musical = 1), so the type depends only on whether all of
    the item's misaligned motor chunks occur in the bases: yes -> 'both', no -> 'musical-only'. Motor chunks become
    untrained at new junctions, and when a trained chunk lands at another position or under another composition and
    is cut differently. Per order, only the first composition that allows the pinned fingering is tried."""
    import itertools
    trained = Trained(bases)
    base_orders = {tuple(b.chunk_ids) for b in bases}
    # every ordering of N_CHUNKS trained chunks with a boundary cue at each junction (graph lookup)
    cand = [t for t in itertools.permutations(trained_chunks, config.N_CHUNKS)
            if all(b in inv.graph[a] for a, b in zip(t, t[1:]))]
    rng.shuffle(cand)
    found: Dict[str, Item] = {}
    for t in cand:
        ids = tuple(ch.chunk_id(c) for c in t)
        if ids in base_orders:
            continue                                  # a base order is trained, not a recombination
        for comp in rng.sample(list(comps), len(comps)):
            # trained chunks must be played exactly as in training: pin the set's fingering
            a = next(valid_assignments(t, comp, inv.opts, fixed=fingering), None)
            if a is None:
                continue
            item = build_item("R", "G", "generalization", "recombined", ids, reg, comp)
            kind = trained.recombination_type(item)   # derived from the proportions, not assumed
            if kind in ("both", "musical-only") and kind not in found:
                item.item_id = "R-" + ("both" if kind == "both" else "musical")
                item.preserved = kind
                found[kind] = item
            break                                     # one composition per order
        if len(found) == 2:
            break
    return found


# ---------------------------------------------------------------------------
# Recombined, motor chunks reordered: motor-only
# ---------------------------------------------------------------------------

def recombined_motor(bases: Sequence[Item], comps, reg: Registry, rng: random.Random,
                     max_nodes: int = 200000) -> Optional[Item]:
    """Trained misaligned motor chunks of the bases, chained in a new order. The item's own musical chunks must
    obey the chunk and boundary rules, neutrality and the string span; at least MOTOR_ONLY_MIN_NEW_MUSICAL of them
    are new (not trained). A musical chunk that happens to be trained keeps its registered fingering. The result
    with the most new musical chunks is returned (the trained proportions are recorded in the item table)."""
    trained = Trained(bases)
    # pool of trained motor chunks AS PLAYED, grouped by length (2 or 3): cut every base by its own composition
    pool: Dict[int, List[Tuple[fb.Pos, ...]]] = {}
    for b in bases:
        for a, e in vs.segments(b.composition):
            seg = tuple(b.positions[a:e])
            pool.setdefault(len(seg), [])
            if seg not in pool[len(seg)]:
                pool[len(seg)].append(seg)
    n = config.CHUNK_LEN
    base_orders = {tuple(b.chunk_ids) for b in bases}

    def chunk_pitches(pos, i):
        """Pitches of musical chunk i (0-based) of a partial or complete position list."""
        return [fb.pitch_of(p.string, p.fret) for p in pos[i * n:(i + 1) * n]]

    def partial_ok(pos: Sequence[fb.Pos], F) -> bool:
        """Can this prefix still become a valid item? Checks only what is already complete: string changes so far
        avoid F (= M delta B), string span, and for every COMPLETE musical chunk: chunk rules, registered fingering
        if it is a trained chunk, cue at the junction with the previous chunk, no repeated chunk."""
        m = len(pos)
        if any(pos[t - 1].string != pos[t].string and t in F for t in range(1, m)):
            return False
        if fb.strings_adjacent_span(pos) > config.MAX_STRING_SPAN:
            return False
        for i in range(m // n):
            pit = chunk_pitches(pos, i)
            cid = ch.chunk_id(pit)
            if ch.within_chunk_problems(pit):
                return False
            if cid in trained.musical and tuple(pos[i * n:(i + 1) * n]) != reg[cid].fingering:
                return False        # same chunk ID, different fingering: not allowed
            if i > 0 and (i + 1) * n <= m and not ch.junction_cues(chunk_pitches(pos, i - 1), pit):
                return False
        ids = [ch.chunk_id(chunk_pitches(pos, i)) for i in range(m // n)]
        return config.ALLOW_CHUNK_REPEAT_IN_ITEM or len(set(ids)) == len(ids)

    best = None   # (n_new, comp, pos)
    for comp in rng.sample(list(comps), len(comps)):
        F = vs.forbidden_crossings(comp)
        nodes = [0]                                   # search budget per composition (list: mutable in rec)

        def rec(k, pos):
            """Fill motor slot k of `comp` with a trained motor chunk of the right length; pos = positions so far."""
            nonlocal best
            if nodes[0] > max_nodes:
                return
            if k == len(comp):                        # all slots filled: a complete 12-note candidate
                ids = tuple(ch.chunk_id(chunk_pitches(pos, i)) for i in range(config.N_CHUNKS))
                n_new = sum(c not in trained.musical for c in ids)
                if ids not in base_orders and n_new >= config.MOTOR_ONLY_MIN_NEW_MUSICAL \
                        and (best is None or n_new > best[0]):
                    best = (n_new, comp, tuple(pos))
                return
            options = list(pool.get(comp[k], []))
            rng.shuffle(options)
            for seg in options:
                nodes[0] += 1
                cand = pos + list(seg)
                if partial_ok(cand, F):
                    rec(k + 1, cand)

        rec(0, [])
    if best is None:
        return None
    # turn the best chain into an item: trained chunks keep their IDs, the others are registered as new
    _, comp, pos = best
    pitches = [fb.pitch_of(p.string, p.fret) for p in pos]
    ids = []
    for i in range(config.N_CHUNKS):
        cid = ch.chunk_id(pitches[i * n:(i + 1) * n])
        ids.append(cid if cid in trained.musical else register_new(reg, tuple(pitches[i * n:(i + 1) * n]), pos[i * n:(i + 1) * n]))
    item = item_from_positions("R-motor", "G", "generalization", "recombined", pos, comp, chunk_ids=ids,
                               preserved="motor-only")
    # trust the proportions, not the intention: only return it if it really is motor-only
    return item if trained.recombination_type(item) == "motor-only" else None


# ---------------------------------------------------------------------------
# Mixed (2 trained + 2 new chunks) and new-chunk items
# ---------------------------------------------------------------------------

def mixed_or_new(inv: Inventory, item_id: str, variant_type: str, n_trained: int,
                 trained_chunks: Sequence[Chunk], fingering: Dict[Chunk, int], comps, reg: Registry,
                 rng: random.Random, tries: int = 20000) -> Optional[Item]:
    """A chunk order from the whole inventory (inv.tuples) with exactly `n_trained` trained chunks:
    n_trained = 2 -> mixed item, 0 -> new-chunk item. Trained chunks keep the set's fingering (pinned); the new
    chunks take whatever the first neutral fingering gives them and are registered as 'new:'. One random composition
    is tried per order; at most `tries` orders. None if nothing works."""
    Pset = set(trained_chunks)
    cands = [t for t in inv.tuples if sum(c in Pset for c in t) == n_trained]
    rng.shuffle(cands)
    for t in cands[:tries]:
        trained = [c for c in t if c in Pset]
        comp = rng.choice(list(comps))
        a = next(valid_assignments(t, comp, inv.opts, fixed={c: fingering[c] for c in trained}), None)
        if a is None:
            continue
        ids = [ch.chunk_id(c) if c in Pset else register_new(reg, c, inv.opts[c][j].positions)
               for c, j in zip(t, a)]
        return build_item(item_id, "G", "generalization", variant_type, ids, reg, comp)
    return None
