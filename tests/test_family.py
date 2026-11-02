"""Family members: alternate fingering, string-pair shift, played transposition, probes, recombined items."""

from tests.helpers import config, expect, fixture, transposable_base

from ukustim.core import versions as vs
from ukustim.family import generalization as gen
from ukustim.family.probes import all_probes
from ukustim.family.trained import Trained
from ukustim.family.transposition import played_transposition


def run():
    fx = fixture()
    base, alt, shift, items = fx.base, fx.alt, fx.shift, fx.items
    if alt:
        moved = sum(a != b for a, b in zip(base.positions, alt.positions))
        expect("alternate item keeps pitches, moves >= 2 notes", alt.pitches == base.pitches and moved >= config.ALT_MIN_NOTES_MOVED)
    if shift:
        expect("string-pair shift changes pitches, keeps frets", shift.pitches != base.pitches
               and [p.fret for p in shift.positions] == [p.fret for p in base.positions])
    probes = all_probes(base)
    expect("three probes, all listen-only", len(probes) == 3 and all(not p.played for p in probes))
    expect("transposition probe has the shifted key", next(p for p in probes if "transposition" in p.variant_type).key == "D")
    acc = next(p for p in probes if "accent" in p.variant_type)
    loud = [i for i, v in enumerate(acc.velocities) if v == config.ACCENT_LOUD]
    expect("accent probe is loud at each misaligned motor chunk start", loud == [a for a, _ in vs.segments(base.composition)])
    # recombined items: type derived from the proportions
    trained = Trained(items)
    rec = [i for i in items if i.variant_type == "recombined"]
    expect("recombined items carry the type derived from their proportions",
           all(trained.recombination_type(i) == i.preserved for i in rec), [(i.item_id, i.preserved, trained.recombination_type(i)) for i in rec])
    for i in rec:
        p = trained.proportions(i)
        if i.preserved == "both":
            expect(f"{i.item_id}: both -> all musical and all misaligned motor chunks trained",
                   p["prop_trained_musical"] == 1 and p["prop_trained_motor_misaligned"] == 1)
        if i.preserved == "musical-only":
            expect(f"{i.item_id}: musical-only -> all musical, not all motor chunks trained",
                   p["prop_trained_musical"] == 1 and p["prop_trained_motor_misaligned"] < 1)
        if i.preserved == "motor-only":
            expect(f"{i.item_id}: motor-only -> all motor chunks trained, not all musical",
                   p["prop_trained_motor_misaligned"] == 1 and p["prop_trained_musical"] < 1)
    # motor-only builder on a set found by search (the fixture set may not support one)
    import random
    from ukustim.selection import objective_search as osr
    inv = fx.inv
    cands = osr.candidates(inv, 2)
    rng = random.Random(5)
    found = None
    for _ in range(400):
        s = osr.sample_solution(inv, cands, 2, 5, 6, rng)
        if not s:
            continue
        ev = osr.evaluate(inv, s)
        m = [i for i in ev.items if i.preserved == "motor-only"]
        if m:
            found = (ev, m[0])
            break
    expect("a motor-only recombined item can be built", found is not None)
    if found:
        ev, m = found
        T = Trained(ev.items)
        expect("motor-only item: every misaligned motor chunk trained, at least one musical chunk new",
               T.proportions(m)["prop_trained_motor_misaligned"] == 1 and T.proportions(m)["prop_trained_musical"] <= 0.75)
        from ukustim.checks import validators as val
        r = val.validate_item(m, {i.item_id: i for i in ev.items})
        expect("motor-only item passes the item checks", all(x.passed for x in r), val.summarize(r))
    # played transposition returns a reason when it is impossible
    b, reg = transposable_base("D")
    config.TRANSPOSITION_KEY = "C"
    t, why = played_transposition(b, reg)
    expect("no transposition into the same key", t is None and "already" in why)
    config.TRANSPOSITION_KEY = "G"
    t, why = played_transposition(fx.by_id["B1"], {})
    expect("a transposition that does not fit first position says why", t is not None or "first position" in why or "neutrality" in why, why)
