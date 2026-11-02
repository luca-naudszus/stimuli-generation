"""
generalization.py
=============================
Generalization layer (build spec section 6): recombined-chunk items (three types, Q10), mixed items
(2 trained + 2 new chunks) and new-chunk items.

  musical-only  trained musical chunks in a new order; crossing motor chunks break
  motor-only    trained misaligned motor chunks in a new order; the musical chunks are new
  both          every musical and every misaligned motor chunk is trained (junction pairs recur)

The type of a recombined item is derived from the trained proportions (family/trained.py), not assumed.
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
    """Registry entry for a chunk outside the trained inventory; same pitches with another fingering get a suffix."""
    base_id = "new:" + ch.chunk_id(pitches)
    cid, k = base_id, 1
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
    """Trained chunks in an order no base uses. Returns {'both': item, 'musical-only': item} (those found)."""
    import itertools
    trained = Trained(bases)
    base_orders = {tuple(b.chunk_ids) for b in bases}
    cand = [t for t in itertools.permutations(trained_chunks, config.N_CHUNKS)
            if all(b in inv.graph[a] for a, b in zip(t, t[1:]))]
    rng.shuffle(cand)
    found: Dict[str, Item] = {}
    for t in cand:
        ids = tuple(ch.chunk_id(c) for c in t)
        if ids in base_orders:
            continue
        for comp in rng.sample(list(comps), len(comps)):
            a = next(valid_assignments(t, comp, inv.opts, fixed=fingering), None)
            if a is None:
                continue
            item = build_item("R", "G", "generalization", "recombined", ids, reg, comp)
            kind = trained.recombination_type(item)
            if kind in ("both", "musical-only") and kind not in found:
                item.item_id = "R-" + ("both" if kind == "both" else "musical")
                item.preserved = kind
                found[kind] = item
            break
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
        return [fb.pitch_of(p.string, p.fret) for p in pos[i * n:(i + 1) * n]]

    def partial_ok(pos: Sequence[fb.Pos], F) -> bool:
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
        nodes = [0]

        def rec(k, pos):
            nonlocal best
            if nodes[0] > max_nodes:
                return
            if k == len(comp):
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
    _, comp, pos = best
    pitches = [fb.pitch_of(p.string, p.fret) for p in pos]
    ids = []
    for i in range(config.N_CHUNKS):
        cid = ch.chunk_id(pitches[i * n:(i + 1) * n])
        ids.append(cid if cid in trained.musical else register_new(reg, tuple(pitches[i * n:(i + 1) * n]), pos[i * n:(i + 1) * n]))
    item = item_from_positions("R-motor", "G", "generalization", "recombined", pos, comp, chunk_ids=ids,
                               preserved="motor-only")
    return item if trained.recombination_type(item) == "motor-only" else None


# ---------------------------------------------------------------------------
# Mixed (2 trained + 2 new chunks) and new-chunk items
# ---------------------------------------------------------------------------

def mixed_or_new(inv: Inventory, item_id: str, variant_type: str, n_trained: int,
                 trained_chunks: Sequence[Chunk], fingering: Dict[Chunk, int], comps, reg: Registry,
                 rng: random.Random, tries: int = 20000) -> Optional[Item]:
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
