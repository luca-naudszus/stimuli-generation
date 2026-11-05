"""Candidate enumeration, objective search, exact-cover search, turning-point cap."""

import random

from tests.helpers import config, expect, fixture

from ukustim.core import chunks as ch
from ukustim.selection import objective_search as osr
from ukustim.selection.solution import turning_cap_ok


def run():
    fx = fixture()
    inv = fx.inv
    # exact-cover set from the fixture: 3 bases, 6 trained chunks, each in exactly 2 bases
    from collections import Counter
    cnt = Counter(c for t, _ in fx.sol.bases for c in t)
    expect("fixture set: 3 bases, 6 chunks, each chunk in exactly 2 bases", len(fx.sol.bases) == 3 and len(cnt) == 6 and set(cnt.values()) == {2})
    # candidates
    cands = osr.candidates(inv, 2)
    expect("candidates: every valid base at degree 2 is enumerated", len(cands) > 1000)
    rng = random.Random(3)
    sols = [s for s in (osr.sample_solution(inv, cands, 2, 4, 6, rng) for _ in range(60)) if s]
    expect("the sampler returns feasible 4-base sets", len(sols) > 0 and all(osr.feasible(inv, s) for s in sols))
    if sols:
        s = sols[0]
        s.bases = s.bases[:-1] + [s.bases[0]]                  # duplicate order: not feasible
        expect("feasibility rejects a repeated base", not osr.feasible(inv, s))
        ev = osr.evaluate(inv, sols[1] if len(sols) > 1 else sols[0])
        expect("evaluation builds the family and a finite objective", 0 <= ev.objective <= 1.3 and len(ev.items) > 8)
        nb = osr.neighbours(inv, cands, sols[-1], rng, 6, n=3)
        expect("neighbour moves stay feasible", all(osr.feasible(inv, x) for x in nb))
    # alternate choice: ties go to MORE moved notes (Q4); exact when every combination is tried
    import itertools
    from ukustim.core.items import ChunkDef, build_item
    from ukustim.family.alternate import alternate_item
    from ukustim.selection.assemble import _choose_alternates
    fx = fixture()
    movable = [(c, [o for j, o in enumerate(fx.inv.opts[c]) if j != fx.sol.fingering[c]]) for c in fx.sol.chunks]
    movable = [(c, a) for c, a in movable if a]
    n_combos = 1
    for _, a in movable:
        n_combos *= len(a) + 1

    def score(reg):
        n_ok = moved = 0
        for bi, (t, comp) in enumerate(fx.sol.bases):
            b = build_item("B", "F", "family", "base", [ch.chunk_id(c) for c in t], reg, comp)
            alt = alternate_item(b, reg)
            if alt:
                n_ok += 1
                moved += sum(x != y for x, y in zip(b.positions, alt.positions))
        return n_ok, moved
    if n_combos <= 5000:
        best = None
        for combo in itertools.product(*[range(len(a) + 1) for _, a in movable]):
            reg = {ch.chunk_id(c): ChunkDef(ch.chunk_id(c), c, fx.inv.opts[c][fx.sol.fingering[c]].positions, None)
                   for c in fx.sol.chunks}
            for (c, a), j in zip(movable, combo):
                if j:
                    reg[ch.chunk_id(c)].alt = a[j - 1].positions
            sc = score(reg)
            best = sc if best is None or sc > best else best
        expect("alternate choice maximises bases with an alternate, then moved notes",
               score(_choose_alternates(fx.inv, fx.sol, random.Random(0), combos_max=n_combos)) == best)
    else:
        print(f"SKIP alternate tie-break test ({n_combos} combinations > 5000)")
    # penalties
    notes = ["B1: no valid alternate fingering", "B2: played transposition to G impossible (x)", "recombined item of type motor-only: none found"]
    expect("missing-member penalties", abs(osr.missing_penalty(notes, 4) - (0.15 + 0.1 / 4 + 0.05)) < 1e-9)
    # turning-point cap
    config.TURNING_POINT_CHUNKS = "allow"
    turning = [(60, 62, 60), (62, 64, 62), (64, 65, 64)]
    plain = [(60, 62, 64), (62, 64, 65), (64, 65, 67)]
    expect("turning-point cap: 2 of 6 allowed at share 1/3", turning_cap_ok(turning[:2] + plain[:2] + plain[2:] + [(65, 67, 69)]))
    expect("turning-point cap: 3 of 6 not allowed at share 1/3", not turning_cap_ok(turning + plain))
    config.TURNING_POINT_CHUNKS = "forbid"
