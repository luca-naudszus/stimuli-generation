"""MIDI, click track, tab, tables, CSV round trip, LilyPond cues."""

import os
import re
import tempfile

from tests.helpers import config, expect, fixture

from ukustim.core import keys
from ukustim.formats import cues, loader, tables
from ukustim.formats.midi import build_click_midi, build_midi
from ukustim.formats.tab import tab_item


def run():
    fx = fixture()
    items, reg, base, alt = fx.items, fx.reg, fx.base, fx.alt
    # --- MIDI --------------------------------------------------------------------------------------------
    try:
        import mido
        with tempfile.TemporaryDirectory() as d:
            for name, data in (("item", build_midi(base)), ("click", build_click_midi(base))):
                p = os.path.join(d, name + ".mid")
                open(p, "wb").write(data)
                mid = mido.MidiFile(p)
                tr = mid.tracks[0]
                tempo = [m.tempo for m in tr if m.type == "set_tempo"][0]
                ts = [m for m in tr if m.type == "time_signature"][0]
                on, t = [], 0
                for m in tr:
                    t += m.time
                    if m.type == "note_on" and m.velocity > 0:
                        on.append((t, m.note, m.velocity))
                expect(f"MIDI {name}: 90 bpm, 3/4, 12 events one beat apart", abs(mido.tempo2bpm(tempo) - config.BPM) < 1e-3
                       and (ts.numerator, ts.denominator) == (3, 4) and len(on) == 12
                       and all(b[0] - a[0] == config.MIDI_PPQ for a, b in zip(on, on[1:])))
                expect(f"MIDI {name}: length 8 s", abs(mid.length - 8.0) < 0.05, f"{mid.length:.3f}")
                if name == "item":
                    expect("MIDI item: notes are the item pitches", [n for _, n, _ in on] == list(base.pitches))
                else:
                    vel = [v for _, _, v in on]
                    expect("MIDI click: accent on beat 1 of each bar", vel == [config.CLICK_VEL_ACCENT if i % 3 == 0 else config.CLICK_VEL_SOFT for i in range(12)])
    except ImportError:
        print("SKIP MIDI round trip (mido not installed)")
    # --- tab ---------------------------------------------------------------------------------------------
    expect("tab header names 3/4 and the key", "3/4" in tab_item(base) and "Key C" in tab_item(base))
    # --- tables ------------------------------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        tables.write_tables(items, d)
        import csv
        notes = list(csv.DictReader(open(os.path.join(d, "note_table.csv"))))
        itm = list(csv.DictReader(open(os.path.join(d, "item_table.csv"))))
        expect("note table: one row per note, spec columns present", len(notes) == 12 * len(items)
               and {"key", "scale_degree", "beat_in_bar", "bar_index", "abstract_chunk_id", "motor_chunk_id_misaligned_lh"} <= set(notes[0]))
        b1 = [r for r in notes if r["item_id"] == "B1"]
        expect("note table: beat_in_bar cycles 1-3, bar_index 1-4", [int(r["beat_in_bar"]) for r in b1] == [1, 2, 3] * 4
               and [int(r["bar_index"]) for r in b1] == [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3)
        expect("note table: scale degrees relative to the item's key", [r["scale_degree"] for r in b1] == [keys.scale_degree(p, "C") for p in base.pitches])
        rows = {r["item_id"]: r for r in itm}
        asg = list(csv.DictReader(open(os.path.join(d, "assignment_template.csv"))))
        expect("assignment template: one row per item, withheld_alternate column (v1.7)",
               len(asg) == len(items) and "withheld_alternate" in asg[0]
               and all((r["withheld_alternate"] == "0") == (r["variant_type"] == "alternate fingering") for r in asg))
        expect("item table: bases are fully trained", rows["B1"]["prop_trained_musical"] == "1.0" and rows["B1"]["prop_trained_motor_misaligned"] == "1.0")
        if alt:
            expect("item table: alternate fingering keeps the musical chunks, not all motor chunks",
                   rows["B1-alt"]["prop_trained_musical"] == "1.0" and float(rows["B1-alt"]["prop_trained_motor_misaligned"]) < 1)
        n1 = rows.get("N1")
        expect("item table: new-chunk item has no trained musical chunk", n1 is None or n1["prop_trained_musical"] == "0.0")
        expect("item table: recombination type recorded for recombined items",
               all(r["recombination_type"] in ("both", "musical-only", "motor-only", "neither") for r in itm if r["variant_type"] == "recombined"))
        loader.save_set(items, reg, os.path.join(d, "in"))
        items2, reg2, _ = loader.load_set(os.path.join(d, "in"))
        same = {i.item_id: (i.pitches, i.positions, i.composition) for i in items if i.variant_type in ("base", "recombined", "mixed", "new-chunk", "alternate fingering", "string-pair shift")} == \
               {i.item_id: (i.pitches, i.positions, i.composition) for i in items2 if i.variant_type in ("base", "recombined", "mixed", "new-chunk", "alternate fingering", "string-pair shift")}
        expect("CSV save / load reproduces the items", same)
    # --- LilyPond cues -----------------------------------------------------------------------------------
    pl = cues.participant_ly(base)
    expect("participant cue: no bar lines, chunk labels or time signature",
           "\\bar" not in pl.replace("\\omit BarLine", "") and "\\markup" not in pl and all(c not in pl for c in base.chunk_ids)
           and "\\omit TimeSignature" in pl)
    strip = lambda s: re.sub(r"\\cadenzaOn [^}]*\}", "", re.sub(r"\\lyricmode \{[^}]*\}", "", s))
    other = next(i for i in items if i.played and i.item_id != base.item_id)
    expect("participant cue: layout identical for every item", strip(pl) == strip(cues.participant_ly(other)))
    fing = re.search(r"\\lyricmode \{ ([^}]*) \}", pl).group(1).split()
    expect("participant cue: finger row shows 0 for open strings", fing == [f'"{p.finger}"' for p in base.positions] and '"0"' in fing)
    expect("participant cue: fixed canvas in the paper block", "paper-width" in pl and "paper-height" in pl)
    rl = cues.researcher_ly(base)
    expect("researcher cue: 3/4 bars hold the chunks, chunk IDs shown", "\\time 3/4" in rl and base.chunk_ids[0] in rl and "cadenzaOn" not in rl)
    expect("LilyPond string numbers A=1 .. G=4 and pitch names", [cues.ly_string(s) for s in "AECG"] == [1, 2, 3, 4]
           and cues.ly_pitch(60) == "c'" and cues.ly_pitch(72) == "c''")
    expect("researcher cue for a transposed item carries its key", "\\key g \\major" in cues.researcher_ly(type(base)(**{**base.__dict__, "key": "G"})))
    if cues.lilypond_binary():
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            sizes = set()
            for it_ in [i for i in items if i.played][:5]:
                p = os.path.join(d, it_.item_id + ".ly")
                open(p, "w").write(cues.participant_ly(it_))
                svg = cues.render(p, "svg", crop=False)
                txt = [t_ for _, _, t_ in cues.svg_fret_digits(svg)]
                frets = [str(q.fret) for q in it_.positions]
                fingers = [str(q.finger) for q in it_.positions]
                expect(f"rendered participant cue {it_.item_id}: fret digits and finger row match the item",
                       sorted(txt) == sorted(frets + fingers), f"{sorted(txt)} vs {sorted(frets + fingers)}")
                xs = sorted({round(x, 2) for x, _, _ in cues.svg_fret_digits(svg)})
                expect(f"rendered participant cue {it_.item_id}: 12 equally spaced columns",
                       len(xs) == config.N_NOTES and len({round(b - a, 2) for a, b in zip(xs, xs[1:])}) == 1)
                png = cues.render(p, "png", dpi=100, crop=False)
                sizes.add(Image.open(png).size)
            expect("participant cues have one fixed canvas size", len(sizes) == 1, str(sizes))
    else:
        print("SKIP rendered cue checks (lilypond not installed)")
