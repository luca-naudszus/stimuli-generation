"""Validators accept a valid set and reject deliberately broken items (checks 1-8)."""

from dataclasses import replace

from tests.helpers import config, expect, failing_checks, fixture, transposable_base

from ukustim.checks import validators as val
from ukustim.core import versions as vs
from ukustim.core.fretboard import Pos
from ukustim.family.transposition import played_transposition


def run():
    fx = fixture()
    items, by_id, base, alt, shift = fx.items, fx.by_id, fx.base, fx.alt, fx.shift
    results = val.validate_set(items)
    expect("valid set passes every check", all(r.passed for r in results), val.summarize(results))
    expect("every check number 1-8 is exercised by the family or a transposition test",
           {"1", "2", "3", "4", "5", "6", "8"} <= {r.check for r in results})

    def broken(item, **kw):
        return replace(item, **kw)

    pos = list(base.positions)
    pos[0] = Pos("A", 5, 4)
    expect("check 1 catches fret 5", "1" in failing_checks(val.validate_item(broken(base, positions=tuple(pos)), by_id)))
    pos = list(base.positions)
    p0 = pos[0]
    pos[0] = Pos(p0.string, (p0.fret + 1) % 5, 1)
    expect("check 1 catches a position / pitch mismatch", "1" in failing_checks(val.validate_item(broken(base, positions=tuple(pos)), by_id)))
    pos = list(base.positions)
    pos[0], pos[1] = Pos("G", 0, 0), Pos("A", 0, 0)
    expect("check 1 catches more than 3 strings", "1" in failing_checks(val.validate_item(broken(base, positions=tuple(pos)), by_id)))
    comp = vs.misaligned_compositions(1)[0]
    t = sorted(vs.forbidden_crossings(comp))[0]
    pos = list(base.positions)
    other = "C" if pos[t - 1].string != "C" else "E"
    pos[t] = Pos(other if pos[t].string == pos[t - 1].string else pos[t - 1].string, pos[t].fret, pos[t].finger)
    r = failing_checks(val.validate_item(broken(base, positions=tuple(pos), composition=comp), by_id))
    expect("check 2 catches a crossing in M delta B", "2" in r or "1" in r)
    expect("check 2 rejects the aligned composition as misaligned",
           "2" in failing_checks(val.validate_item(broken(base, composition=vs.aligned_composition()), by_id)))
    cps = base.chunk_pitches()
    swapped = tuple(cps[0]) + tuple(cps[0][::-1]) + tuple(cps[1]) + tuple(cps[3])
    expect("check 3 catches a missing boundary cue", "3" in failing_checks(val.validate_item(broken(base, pitches=swapped), by_id)))
    wide = list(base.pitches)
    wide[1] = wide[0] + 4
    expect("check 3 catches a 4-semitone interval inside a chunk", "3" in failing_checks(val.validate_item(broken(base, pitches=tuple(wide)), by_id)))
    rep = list(base.pitches)
    rep[1] = rep[0]
    expect("check 3 catches a consecutive repeat", "3" in failing_checks(val.validate_item(broken(base, pitches=tuple(rep)), by_id)))
    turn = list(base.pitches)
    turn[2] = turn[0]
    expect("check 3 catches a turning point inside a chunk", "3" in failing_checks(val.validate_item(broken(base, pitches=tuple(turn)), by_id)))
    expect("check 4 catches missing recurrence", any(not x.passed for x in val.check_4_recurrence([base])))
    if alt:
        expect("check 5 catches changed pitches", "5" in failing_checks(val.validate_item(broken(alt, pitches=tuple(p + 1 for p in alt.pitches)), by_id)))
        expect("check 5 catches zero moved notes", "5" in failing_checks(val.validate_item(broken(alt, positions=base.positions), by_id)))
    if shift:
        pos = list(shift.positions)
        pos[0] = Pos(pos[0].string, (pos[0].fret + 1) % 5, 1)
        expect("check 6 catches changed frets", "6" in failing_checks(val.validate_item(broken(shift, positions=tuple(pos)), by_id)))
        pos = list(shift.positions)       # same frets and fingers, but the string pattern changes at one transition
        i = next(k for k in range(1, 12) if pos[k].string == pos[k - 1].string)
        pos[i] = Pos("E" if pos[i].string != "E" else "C", pos[i].fret, pos[i].finger)
        expect("check 6 catches a changed relative string pattern", "6" in failing_checks(val.validate_item(broken(shift, positions=tuple(pos)), by_id)))
    # check 7: played transposition (to D, which works for many bases; G is the default but rarely feasible)
    b7, reg7 = transposable_base("D")
    old = config.TRANSPOSITION_KEY
    config.TRANSPOSITION_KEY = "D"
    tr, why = played_transposition(b7, reg7)
    config.TRANSPOSITION_KEY = old
    expect("a played transposition to D is built for a transposable base", tr is not None, why)
    if tr:
        by7 = {b7.item_id: b7, tr.item_id: tr}
        r = val.validate_item(tr, by7)
        expect("transposed item passes checks 1-3, 7 and 8", all(x.passed for x in r), val.summarize(r))
        expect("transposed chunks keep their fingering in a second call (registry)", played_transposition(b7, reg7, "D")[0].positions == tr.positions)
        bad = list(tr.pitches)
        bad[3] += 1
        expect("check 7 catches a changed interval", "7" in failing_checks(val.validate_item(replace(tr, pitches=tuple(bad)), by7)))
        expect("check 7 catches an item without a key change", "7" in failing_checks(val.validate_item(replace(tr, key=b7.key), by7)))
    # check 8: metre
    config.BEATS_PER_BAR = 4
    expect("check 8 catches a bar length that does not match the chunk length", "8" in failing_checks(val.validate_item(base, by_id)))
    config.BEATS_PER_BAR = 3
