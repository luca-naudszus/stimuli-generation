"""
assemble.py
=============================
From a solution (trained chunks, fingering, bases) to the full list of items: bases, alternate fingering,
string-pair shift, played transposition, probes, recombined (musical-only / motor-only / both), mixed and
new-chunk items. Notes list what could not be built and why.

Order of work in assemble_family:
  1. choose one alternate fingering per trained chunk (_choose_alternates) -> the registry
  2. build the bases from the registry
  3. per base: alternate item, string-pair shift, played transposition, probes
  4. generalization layer: recombined (musical-only / both, then motor-only), mixed, new-chunk
Everything that cannot be built is recorded in `notes` (shown in report.txt) instead of failing.
"""

import itertools
import random
from typing import Dict, List, Tuple

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import versions as vs
from ukustim.core.inventory import Inventory
from ukustim.core.items import ChunkDef, Item, Registry, build_item
from ukustim.family import generalization as gen
from ukustim.family.alternate import alternate_item
from ukustim.family.probes import all_probes
from ukustim.family.string_shift import string_pair_shift
from ukustim.family.transposition import played_transposition
from ukustim.selection.solution import Solution


def _choose_alternates(inv: Inventory, sol: Solution, rng: random.Random, combos_max: int = 400):
    """Pick one alternate fingering per chunk (or none) so that as many bases as possible get a valid
    alternate item; ties go to the choice that moves MORE notes in the alternate items (build spec section 5, Q4:
    "as many as neutrality and the band allow"). Returns the registry.

    Each chunk with more than one fingering option can take any other option as its alternate, or none (index 0 in
    a combo = no alternate, j > 0 = alts[j - 1]). All combinations are listed, shuffled, and at most combos_max are
    scored by building every base's alternate item. Score = (bases with an alternate item, moved notes in total).
    The alternate must be chosen per chunk, not per item, because a chunk has one alternate wherever it appears."""
    reg: Registry = {}
    movable = []                       # (chunk, its other fingering options)
    for c in sol.chunks:
        base_opt = inv.opts[c][sol.fingering[c]]
        alts = [o for j, o in enumerate(inv.opts[c]) if j != sol.fingering[c]]
        reg[ch.chunk_id(c)] = ChunkDef(ch.chunk_id(c), c, base_opt.positions, None, "trained")
        if alts:
            movable.append((c, alts))
    best_score, best_reg = None, None
    ranges = [range(len(alts) + 1) for _, alts in movable]
    combos = list(itertools.product(*ranges))
    rng.shuffle(combos)
    for combo in combos[:combos_max]:
        # fresh copy of the registry without alternates, then set the alternates of this combination
        r2 = {k: ChunkDef(v.chunk_id, v.pitches, v.fingering, None, v.role) for k, v in reg.items()}
        for (c, alts), j in zip(movable, combo):
            if j > 0:
                r2[ch.chunk_id(c)].alt = alts[j - 1].positions
        n_ok, moved_items = 0, 0
        for bi, (t, comp) in enumerate(sol.bases):
            base = build_item(f"B{bi + 1}", f"F{bi + 1}", "family", "base", [ch.chunk_id(c) for c in t], r2, comp)
            a = alternate_item(base, r2)
            if a is not None:
                n_ok += 1
                moved_items += sum(x != y for x, y in zip(base.positions, a.positions))
        score = (n_ok, moved_items)
        if best_score is None or score > best_score:
            best_score, best_reg = score, r2
    return best_reg if best_reg is not None else reg


def assemble_family(inv: Inventory, sol: Solution, seed: int = 0, with_new_chunk_item: bool = True,
                    alt_combos: int = 400) -> Tuple[List[Item], Registry, List[str]]:
    """Full item list for a solution + notes about what could not be built.
    Returns (items, registry, notes). Item IDs: B1..Bk bases, Bk-alt, Bk-shift, Bk-tr, Bk-p-<type> probes,
    R-both, R-musical, R-motor, X1 (mixed), N1 (new-chunk). The seed makes the random choices reproducible.
    Called by the search for every evaluated set and by report_set for the final one."""
    rng = random.Random(config.SEED + seed)
    notes: List[str] = []
    reg = _choose_alternates(inv, sol, rng, alt_combos)
    items: List[Item] = []
    bases: List[Item] = []
    for bi, (t, comp) in enumerate(sol.bases):
        b = build_item(f"B{bi + 1}", f"F{bi + 1}", "family", "base", [ch.chunk_id(c) for c in t], reg, comp)
        bases.append(b)
        items.append(b)
    for b in bases:
        a = alternate_item(b, reg)
        if a:
            items.append(a)
        else:
            notes.append(f"{b.item_id}: no valid alternate fingering")
        s = string_pair_shift(b)
        if s:
            items.append(s)
        else:
            notes.append(f"{b.item_id}: string-pair shift impossible (strings do not fit)")
        tr, why = played_transposition(b, reg)
        if tr:
            items.append(tr)
        else:
            notes.append(f"{b.item_id}: played transposition to {config.TRANSPOSITION_KEY} impossible ({why})")
        items.extend(all_probes(b))
    # generalization layer: items made across families, from the set's trained chunks
    comps = vs.misaligned_compositions(sol.degree)
    found = gen.recombined_musical(inv, bases, sol.chunks, sol.fingering, comps, reg, rng)
    for kind in ("both", "musical-only"):
        if kind in found:
            items.append(found[kind])
        else:
            notes.append(f"recombined item of type {kind}: none found")
    motor = gen.recombined_motor(bases, comps, reg, rng)
    if motor:
        items.append(motor)
    else:
        notes.append("recombined item of type motor-only: none found")
    m = gen.mixed_or_new(inv, "X1", "mixed", 2, sol.chunks, sol.fingering, comps, reg, rng)
    if m:
        items.append(m)
    else:
        notes.append("mixed item: none found")
    if with_new_chunk_item:
        n = gen.mixed_or_new(inv, "N1", "new-chunk", 0, sol.chunks, sol.fingering, comps, reg, rng)
        if n:
            items.append(n)
        else:
            notes.append("new-chunk item: none found")
    return items, reg, notes
