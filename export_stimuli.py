"""
export_stimuli.py
=============================
Exports selected stimuli as ASCII tablature (.txt) and MIDI (.mid), one file each per stimulus,
plus one combined tab file per set. Frets/strings come straight from the vocabularies; MIDI
pitches from chord_sounding_midi (chords) and TONE_VOCAB (melodies).
Timing comes from config: bar duration, beats per bar, note length. No external libraries.
"""

import csv
import math
import os
from typing import Dict, List, Sequence

import config
from chord_vocab import CHORD_VOCAB
from tone_vocab import TONE_VOCAB
from harmonic_distance import chord_sounding_midi

TAB_ORDER = ("A", "E", "C", "G")     # ukulele tab: top line = A string, bottom line = G string
MELODY_COL_W = 4
CHORD_BAR_W = 16


def _bpm() -> float:
    return 60.0 * config.BEATS_PER_BAR / config.BAR_DURATION_S


def _tempo_line(kind: str) -> str:
    note = {1.0: "quarter notes", 0.5: "eighth notes", 2.0: "half notes"}.get(
        config.MELODY_NOTE_BEATS, f"notes of {config.MELODY_NOTE_BEATS} beat(s)")
    what = note if kind == "melodies" else (
        "one chord per bar" if config.CHORD_BARS == 1 else f"one chord per {config.CHORD_BARS} bars")
    return (f"Tempo: {_bpm():g} bpm, {config.BEATS_PER_BAR}/4 "
            f"(1 bar = {config.BAR_DURATION_S:g} s), {what}")


def _cell(fret: int) -> str:
    return "-" + str(fret).ljust(2, "-") + "-"


# ---------------------------------------------------------------------------
# Tablature
# ---------------------------------------------------------------------------

def tab_melody(stim_id: str, tone_ids: Sequence[str]) -> str:
    lines = {s: [] for s in TAB_ORDER}
    names = []
    beats = 0.0
    bpb = config.BEATS_PER_BAR
    for t in tone_ids:
        if beats > 1e-9 and (math.isclose(beats % bpb, 0, abs_tol=1e-9) or
                             math.isclose(beats % bpb, bpb, abs_tol=1e-9)):
            for s in TAB_ORDER:
                lines[s].append("|")
            names.append(" ")
        string, fret = TONE_VOCAB[t]["position"]
        for s in TAB_ORDER:
            lines[s].append(_cell(fret) if s == string else "-" * MELODY_COL_W)
        names.append((" " + TONE_VOCAB[t]["label"]).ljust(MELODY_COL_W))
        beats += config.MELODY_NOTE_BEATS
    head = [f"{stim_id}  (melody)", _tempo_line("melodies"), ""]
    body = ["  " + "".join(names)] + [f"{s}|" + "".join(lines[s]) + "|" for s in TAB_ORDER]
    return "\n".join(head + body) + "\n"


def tab_progression(stim_id: str, chord_ids: Sequence[str]) -> str:
    width = CHORD_BAR_W * config.CHORD_BARS
    names = "".join(c.ljust(width + 1) for c in chord_ids)
    body = ["  " + names.rstrip()]
    for s in TAB_ORDER:
        bars = []
        for c in chord_ids:
            fret = CHORD_VOCAB[c]["shape"][s]
            bars.append(("-----" + str(fret).ljust(2, "-")).ljust(width, "-"))
        body.append(f"{s}|" + "|".join(bars) + "|")
    head = [f"{stim_id}  (chord progression)", _tempo_line("progressions"), ""]
    return "\n".join(head + body) + "\n"


# ---------------------------------------------------------------------------
# MIDI (Standard MIDI File, format 0)
# ---------------------------------------------------------------------------

def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def build_midi(events: List[tuple], name: str) -> bytes:
    """events: (start_tick, duration_ticks, [midi pitches])."""
    ppq = config.MIDI_PPQ
    ev = []
    for start, dur, pitches in events:
        for p in pitches:
            ev.append((start, 1, bytes([0x90, p, config.MIDI_VELOCITY])))
            ev.append((start + dur, 0, bytes([0x80, p, 0])))
    ev.sort(key=lambda e: (e[0], e[1]))               # note-off before note-on at equal ticks
    nb = name.encode("ascii", "replace")
    tr = bytearray(b"\x00\xFF\x03" + _vlq(len(nb)) + nb)
    tr += b"\x00\xFF\x51\x03" + round(60_000_000 / _bpm()).to_bytes(3, "big")
    tr += b"\x00\xFF\x58\x04" + bytes([config.BEATS_PER_BAR, 2, 24, 8])
    tr += b"\x00\xC0" + bytes([config.MIDI_PROGRAM])
    last = 0
    for tick, _, data in ev:
        tr += _vlq(tick - last) + data
        last = tick
    tr += b"\x00\xFF\x2F\x00"
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    return header + b"MTrk" + len(tr).to_bytes(4, "big") + bytes(tr)


def midi_melody(stim_id: str, tone_ids: Sequence[str]) -> bytes:
    dur = round(config.MELODY_NOTE_BEATS * config.MIDI_PPQ)
    return build_midi([(i * dur, dur, [TONE_VOCAB[t]["midi"]]) for i, t in enumerate(tone_ids)], stim_id)


def midi_progression(stim_id: str, chord_ids: Sequence[str]) -> bytes:
    dur = config.CHORD_BARS * config.BEATS_PER_BAR * config.MIDI_PPQ
    return build_midi([(i * dur, dur, chord_sounding_midi(CHORD_VOCAB[c]["shape"]))
                       for i, c in enumerate(chord_ids)], stim_id)


# ---------------------------------------------------------------------------
# Export of whole sets
# ---------------------------------------------------------------------------

def read_selected(path: str) -> List[Dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def export_kind(kind: str, rows: List[Dict], out_dir: str = config.STIMULI_DIR) -> int:
    tab_fn, midi_fn = (tab_progression, midi_progression) if kind == "progressions" else (tab_melody, midi_melody)
    combined: Dict[str, List[str]] = {}
    for r in rows:
        ids = r["sequence"].split(" | ")
        d = os.path.join(out_dir, kind, r["set"])
        os.makedirs(d, exist_ok=True)
        tab = tab_fn(r["stimulus_id"], ids)
        with open(os.path.join(d, r["stimulus_id"] + ".txt"), "w", encoding="utf-8") as f:
            f.write(tab)
        with open(os.path.join(d, r["stimulus_id"] + ".mid"), "wb") as f:
            f.write(midi_fn(r["stimulus_id"], ids))
        combined.setdefault(r["set"], []).append(tab)
    for set_name, tabs in combined.items():
        with open(os.path.join(out_dir, kind, f"{kind}_set{set_name}_all_tabs.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(tabs))
    return len(rows)


def export_all(out_dir: str = config.STIMULI_DIR) -> None:
    for kind in ("progressions", "melodies"):
        rows = read_selected(os.path.join(out_dir, f"selected_{kind}.csv"))
        n = export_kind(kind, rows, out_dir)
        print(f"{n} {kind} exported (.txt + .mid) -> {out_dir}/{kind}/")