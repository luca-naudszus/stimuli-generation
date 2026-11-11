"""
transposition.py
=============================
Played transposition (build spec section 5): the base melody in another key that fits first position
(default C major -> G major), played with the fingering that key needs. Movement and concrete sound change,
the abstract structure (intervals, contour, scale degrees) stays.

Rules checked here and again by the validators (check 7): every interval kept; frets 0-4; at most 3 adjacent
strings; neutrality rule with the base's composition; boundary cues (kept automatically, the intervals are the
same). Fingering is chosen per chunk and kept in the registry, so a transposed chunk is fingered the same way
in every transposed item. Report per base whether a transposition is feasible and why not.

How a transposition is found:
  1. keys.transposition_offsets: the semitone shifts to the target key that keep every pitch in C4..C#5;
  2. for each shift (smallest first), cut the shifted melody into its 4 chunks and search neutral fingerings with
     the BASE's composition (core/fingering.valid_assignments), pinning transposed chunks that are already registered;
  3. take the fingering with the lowest frets (sum of frets, then lowest option indices) and register its chunks.
"""

from typing import Dict, List, Optional, Tuple

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import keys
from ukustim.core.fingering import positions_of, valid_assignments
from ukustim.core.items import ChunkDef, Item, Registry, item_from_positions


def transposed_chunk_id(pitches, key: str) -> str:
    """Registry ID of a transposed chunk, e.g. 'new:D:D4-E4-F#4'. 'new:' because it was never practised;
    the key keeps transposed chunks of different target keys apart."""
    return f"new:{key}:{ch.chunk_id(pitches)}"


def played_transposition(base: Item, registry: Registry, target_key: Optional[str] = None
                         ) -> Tuple[Optional[Item], str]:
    """Returns (item or None, reason). Adds the transposed chunks' fingerings to `registry` (role 'transposed').
    The reason is either the shift used ('+2 semitones') or why no transposition exists (shown in the report)."""
    target = target_key or config.TRANSPOSITION_KEY
    if base.key is None:
        return None, "base has no key"
    if base.key == target:
        return None, f"base is already in {target}"
    offsets = keys.transposition_offsets(base.pitches, base.key, target)
    if not offsets:
        return None, f"no shift to {target} keeps every pitch in first position"
    n = config.CHUNK_LEN
    why = []
    for s in offsets:
        moved = [p + s for p in base.pitches]
        chunks = tuple(tuple(moved[i * n:(i + 1) * n]) for i in range(config.N_CHUNKS))
        # the transposed chunks are not in the inventory, so their fingering options are computed here
        opts = {c: ch.fingering_options(c) for c in chunks}
        # pin chunks that an earlier transposition already registered (same chunk = same fingering);
        # `fixed` needs an index into THIS opts list, so find the option with the registered positions
        fixed: Dict[Tuple[int, ...], int] = {}
        for c in chunks:
            d = registry.get(transposed_chunk_id(c, target))
            if d is not None:
                fixed[c] = next(j for j, o in enumerate(opts[c]) if o.positions == d.fingering)
        # among all neutral fingerings, keep the one with the lowest frets (easiest, closest to first-position habit)
        found = None
        for a in valid_assignments(chunks, base.composition, opts, fixed):
            pos = positions_of(chunks, a, opts)
            cost = (sum(p.fret for p in pos), sum(a))
            if found is None or cost < found[0]:
                found = (cost, a, pos)
        if found is None:
            why.append(f"{s:+d} semitones: no fingering satisfies neutrality for composition "
                       f"{'-'.join(map(str, base.composition))} within {config.MAX_STRING_SPAN} strings")
            continue
        _, a, pos = found
        # register the transposed chunks (setdefault: keep an existing entry, which is identical because pinned)
        ids = []
        for c, j in zip(chunks, a):
            cid = transposed_chunk_id(c, target)
            registry.setdefault(cid, ChunkDef(cid, c, opts[c][j].positions, None, "transposed"))
            ids.append(cid)
        item = item_from_positions(f"{base.item_id}-tr", base.family_id, "family", "played transposition", pos,
                                   base.composition, base.item_id, key=target, chunk_ids=ids,
                                   meta={"shift_semitones": str(s)})
        return item, f"{s:+d} semitones"
    return None, "; ".join(why)


def has_transposition(pitches, comp, key_from: str, key_to: str) -> bool:
    """True if some shift to key_to keeps first position and allows a neutral fingering (no registry constraint).
    Cheap feasibility test used by the search (Cand.transposable) and by feasibility_by_key."""
    n = config.CHUNK_LEN
    for s in keys.transposition_offsets(pitches, key_from, key_to):
        moved = [p + s for p in pitches]
        cs = tuple(tuple(moved[i * n:(i + 1) * n]) for i in range(config.N_CHUNKS))
        o = {c: ch.fingering_options(c) for c in cs}
        if next(valid_assignments(cs, comp, o), None) is not None:
            return True
    return False


def feasibility_by_key(inv, deg: int, target_keys=None) -> Dict[str, Dict]:
    """For every valid base (chunk order x misaligned composition of degree `deg` with a neutral fingering),
    whether a played transposition to each target key exists (shift keeps first position, neutrality holds).
    Returns {key: {'feasible': n, 'valid_bases': N, 'orders': number of distinct chunk orders with a feasible base}}.
    Built to inform the choice of config.TRANSPOSITION_KEY (the range C4-C#5 limits which shifts are possible);
    called by `python main.py transpositions` (Q11)."""
    from ukustim.core import versions as vs
    from ukustim.core.music_theory import NOTE_NAMES
    target_keys = target_keys or [k for k in NOTE_NAMES if k != (config.KEY or "")]
    n = config.CHUNK_LEN
    comps = vs.misaligned_compositions(deg)
    out = {k: dict(feasible=0, valid_bases=0, orders=set()) for k in target_keys}
    for t in inv.tuples:
        pitches = [p for c in t for p in c]
        for comp in comps:
            if next(valid_assignments(t, comp, inv.opts), None) is None:
                continue                                  # not a valid base at all
            for k in target_keys:
                out[k]["valid_bases"] += 1
                if has_transposition(pitches, comp, config.KEY, k):
                    out[k]["feasible"] += 1
                    out[k]["orders"].add(t)
    for k in out:
        out[k]["orders"] = len(out[k]["orders"])
    return out
