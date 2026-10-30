"""
tests.py   (run: python tests.py)
=============================
Checks that the validators accept a valid set and reject deliberately broken items, plus MIDI round trip.
"""

import copy
import os
import sys
import tempfile
from dataclasses import replace

import config
import chunks as ch
import cues
import export as ex
import feasibility as fz
import fretboard as fb
import items as it
import loader
import tables
import validators as val
import versions as vs
from fretboard import Pos

FAILED = []


def expect(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


def failing_checks(results):
    return sorted({r.check for r in results if not r.passed})


def main():
    # --- enumeration -------------------------------------------------------
    inv = fz.Inventory()
    expect("26 chunks in C major (12 monotonic)", len(inv.chunks) == 26 and sum(ch.is_monotonic(c) for c in inv.chunks) == 12)
    P = lambda *n: tuple(fb.available_pitches()[i] for i in n)   # indices into C4..C5
    # C4 D4 E4 | G4 A4 B4 : boundary E4->G4 = 3 semitones, within-chunk 2 -> leap cue
    expect("leap cue (+3) accepted", ch.junction_cues(P(0, 1, 2), P(4, 5, 6)) == {"leap"})
    # C4 D4 E4 | D4 C4 ... boundary -2 after an upward chunk -> direction cue with monotonic chunks
    expect("direction cue accepted", ch.junction_cues((60, 62, 64), (62, 60, 59)) == {"direction"})
    expect("direction cue needs monotonic chunks", ch.junction_cues((60, 62, 64), (62, 64, 62)) == set())
    expect("no cue for step in same direction", ch.junction_cues(P(0, 1, 2), P(3, 4, 5)) == set())
    expect("repeated note across the boundary has no cue", ch.junction_cues(P(0, 1, 2), P(2, 3, 4)) == set())
    expect("leap above LEAP_MAX rejected", ch.junction_cues(P(0, 1, 2), (fb.available_pitches()[2] + 8, fb.available_pitches()[2] + 10, fb.available_pitches()[2] + 12)) == set())
    expect("chunk with a 3-semitone interval is invalid", bool(ch.within_chunk_problems((60, 64, 65))))
    expect("chunk with consecutive repeat is invalid", bool(ch.within_chunk_problems((60, 60, 62))))
    expect("chunk C-D-C (turning point, no repeat) is valid", not ch.within_chunk_problems((60, 62, 60)))

    # --- a valid set -------------------------------------------------------
    config.MISALIGNMENT_DEGREE = 1
    sols, _ = fz.find_sets(inv, 1, trials=400, want=1)
    expect("search finds a set at degree 1", bool(sols))
    items, reg, notes = fz.assemble_family(inv, sols[0])
    results = val.validate_set(items)
    expect("valid set passes every check", all(r.passed for r in results), val.summarize(results))
    by_id = {i.item_id: i for i in items}
    base = by_id["B1"]
    alt = by_id.get("B1-alt")
    shift = by_id.get("B1-shift")

    # --- broken items ------------------------------------------------------
    def broken(item, **kw):
        return replace(item, **kw)

    # check 1: fret above 4
    pos = list(base.positions)
    pos[0] = Pos("A", 5, 4)
    r = val.validate_item(broken(base, positions=tuple(pos)), by_id)
    expect("check 1 catches fret 5", "1" in failing_checks(r))
    # check 1: pitch/position mismatch
    pos = list(base.positions)
    p0 = pos[0]
    pos[0] = Pos(p0.string, (p0.fret + 1) % 5, 1)
    r = val.validate_item(broken(base, positions=tuple(pos)), by_id)
    expect("check 1 catches position/pitch mismatch", "1" in failing_checks(r))
    # check 1: four adjacent strings
    pos = list(base.positions)
    pos[0] = Pos("G", 0, 0)
    pos[1] = Pos("A", 0, 0)
    r = val.validate_item(broken(base, positions=tuple(pos)), by_id)
    expect("check 1 catches > 3 strings", "1" in failing_checks(r))
    # check 2: crossing at a forbidden transition (note 3 -> 4 is a musical boundary at degree 1 if not in B)
    comp = vs.misaligned_compositions(1)[0]
    forb = sorted(vs.forbidden_crossings(comp))
    pos = list(base.positions)
    t = forb[0]
    other = "C" if pos[t - 1].string != "C" else "E"
    pos[t] = Pos(other if pos[t].string == pos[t - 1].string else pos[t - 1].string, pos[t].fret, pos[t].finger)
    r = val.validate_item(broken(base, positions=tuple(pos), composition=comp), by_id)
    expect("check 2 catches a crossing in M delta B", "2" in failing_checks(r) or "1" in failing_checks(r))
    # check 2: composition equal to aligned
    r = val.validate_item(broken(base, composition=vs.aligned_composition()), by_id)
    expect("check 2 rejects the aligned composition as misaligned", "2" in failing_checks(r))
    # check 3: swap two chunks -> some boundary has no cue
    cps = base.chunk_pitches()
    swapped = tuple(cps[0]) + tuple(cps[0][::-1]) + tuple(cps[1]) + tuple(cps[3])
    r = val.validate_item(broken(base, pitches=swapped), by_id)
    expect("check 3 catches missing boundary cue", "3" in failing_checks(r))
    # check 3: competing cue inside a chunk
    wide = list(base.pitches)
    wide[1] = wide[0] + 4
    r = val.validate_item(broken(base, pitches=tuple(wide)), by_id)
    expect("check 3 catches a 4-semitone interval inside a chunk", "3" in failing_checks(r))
    rep = list(base.pitches)
    rep[1] = rep[0]
    r = val.validate_item(broken(base, pitches=tuple(rep)), by_id)
    expect("check 3 catches a consecutive repeat inside a chunk", "3" in failing_checks(r))
    # check 4: a set with a single base cannot recur
    r = val.check_4_recurrence([base])
    expect("check 4 catches missing recurrence", any(not x.passed for x in r))
    # check 5: alternate with a changed pitch / too few moved notes
    if alt:
        r = val.validate_item(broken(alt, pitches=tuple(p + 1 for p in alt.pitches)), by_id)
        expect("check 5 catches changed pitches", "5" in failing_checks(r))
        r = val.validate_item(broken(alt, positions=base.positions), by_id)
        expect("check 5 catches zero moved notes", "5" in failing_checks(r))
    # check 6: shift with changed frets
    if shift:
        pos = list(shift.positions)
        pos[0] = Pos(pos[0].string, (pos[0].fret + 1) % 5, 1)
        r = val.validate_item(broken(shift, positions=tuple(pos)), by_id)
        expect("check 6 catches changed frets", "6" in failing_checks(r))

    # --- MIDI round trip ---------------------------------------------------
    try:
        import mido
        data = ex.build_midi(base)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            f.write(data)
        mid = mido.MidiFile(f.name)
        tempo = [m.tempo for m in mid.tracks[0] if m.type == "set_tempo"][0]
        on = [(sum(m.time for m in mid.tracks[0][:k + 1]), m.note) for k, m in enumerate(mid.tracks[0]) if m.type == "note_on" and m.velocity > 0]
        expect("MIDI tempo is 90 bpm", abs(mido.tempo2bpm(tempo) - config.BPM) < 1e-3)
        expect("MIDI has 12 notes with the item pitches", [n for _, n in on] == list(base.pitches))
        expect("MIDI notes are one beat apart", all(b[0] - a[0] == config.MIDI_PPQ for a, b in zip(on, on[1:])))
        expect("MIDI length = 8 s", abs(mid.length - 8.0) < 0.05, f"{mid.length:.3f}")
    except ImportError:
        print("SKIP MIDI round trip (mido not installed)")

    # --- tables + CSV round trip --------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        tables.write_tables(items, d)
        rows = open(os.path.join(d, "note_table.csv")).read().splitlines()
        n_played = sum(1 for i in items if i.played)
        expect("note table has one row per note", len(rows) - 1 == 12 * len(items))
        loader.save_set(items, reg, os.path.join(d, "in"))
        items2, reg2, _ = loader.load_set(os.path.join(d, "in"))
        ok = {i.item_id: (i.pitches, i.positions, i.composition) for i in items} == \
             {i.item_id: (i.pitches, i.positions, i.composition) for i in items2}
        expect("CSV save/load reproduces every item", ok)

    # --- LilyPond cues --------------------------------------------------------
    pl = cues.participant_ly(base)
    expect("participant cue has no bar lines / time signature / chunk labels",
           "\\bar" not in pl.replace("\\omit BarLine", "") and "\\markup" not in pl and
           all(cid not in pl for cid in base.chunk_ids) and "\\omit TimeSignature" in pl)
    # layout must not depend on the item: removing the notes and finger rows leaves identical text
    import re
    strip = lambda s: re.sub(r"\\cadenzaOn [^}]*\}", "", re.sub(r'\\lyricmode \{[^}]*\}', "", s))
    other = next(i for i in items if i.played and i.item_id != base.item_id)
    expect("participant layout is identical for every item", strip(pl) == strip(cues.participant_ly(other)))
    rl = cues.researcher_ly(base)
    expect("researcher cue has chunk bars and chunk IDs", rl.count('\\bar "|"') == config.N_CHUNKS - 1 and base.chunk_ids[0] in rl)
    expect("LilyPond string numbers: A=1 .. G=4", [cues.ly_string(s) for s in "AECG"] == [1, 2, 3, 4])
    expect("LilyPond pitch names", cues.ly_pitch(60) == "c'" and cues.ly_pitch(69) == "a'" and cues.ly_pitch(72) == "c''")
    if cues.lilypond_binary():
        with tempfile.TemporaryDirectory() as d:
            for it_ in (base, alt):
                if it_ is None:
                    continue
                p = os.path.join(d, it_.item_id + ".ly")
                open(p, "w").write(cues.participant_ly(it_))
                svg = cues.render(p, "svg")
                txt = [t_ for _, _, t_ in cues.svg_fret_digits(svg)]
                frets = [str(q.fret) for q in it_.positions]
                fingers = [str(q.finger) for q in it_.positions if q.finger > 0]
                expect(f"rendered participant cue {it_.item_id}: fret digits = item frets, fingers = item fingers",
                       [t_ for t_ in txt if t_ in "01234"] != [] and sorted(txt) == sorted(frets + fingers),
                       f"{txt} vs {frets} {fingers}")
                xs = sorted({round(x, 2) for x, _, _ in cues.svg_fret_digits(svg)})
                gaps = {round(b - a, 2) for a, b in zip(xs, xs[1:])}
                expect(f"rendered participant cue {it_.item_id}: 12 equally spaced columns (no spacing cue)",
                       len(xs) == config.N_NOTES and len(gaps) == 1, f"{len(xs)} columns, gaps {gaps}")
    else:
        print("SKIP rendered cue check (lilypond not installed)")

    print("\n%d failed" % len(FAILED) if FAILED else "\nall tests passed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
