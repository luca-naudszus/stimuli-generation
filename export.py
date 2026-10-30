"""
export.py
=============================
ASCII tab with left-hand fingers and chunk markers, and Standard MIDI File (format 0) at config.BPM.
No external libraries.
"""

import os
from typing import List, Sequence

import config
import fretboard as fb
import versions as vs
from items import Item

TAB_ORDER = ("A", "E", "C", "G")    # ukulele tab: top line = A string
COL = 4


def _letters(comp: Sequence[int]) -> List[str]:
    """One letter per note: letter changes at every motor chunk."""
    out = []
    for k, p in enumerate(comp):
        out += [chr(ord("A") + k)] * p
    return out


def _spaced(cells: Sequence[str], sep_after) -> str:
    """Join cells (COL wide); insert '|' after the note indices in sep_after."""
    parts = []
    for i, c in enumerate(cells):
        parts.append(c.ljust(COL)[:COL] if len(c) <= COL else c)
        if i in sep_after:
            parts.append("|")
    return "".join(parts)


def tab_item(item: Item) -> str:
    n = config.CHUNK_LEN
    sep = {n * k - 1 for k in range(1, config.N_CHUNKS)}
    head = [f"{item.item_id}  ({item.variant_type}; family {item.family_id}; layer {item.layer})",
            f"Key {config.KEY or 'chromatic'}, {config.BPM} bpm, 4/4, one note per beat "
            f"(1 chunk = {60 * n / config.BPM:g} s, item = {60 * config.N_NOTES / config.BPM:g} s)",
            "Musical chunks: " + " | ".join(item.chunk_ids), ""]
    names = [" " + fb.pitch_name(p) for p in item.pitches]
    body = ["    " + _spaced(names, sep)]
    if not item.played:
        body.append("   (listen-only: no fingering)")
        if item.velocities:
            body.append("   velocity: " + " ".join(str(v) for v in item.velocities))
        return "\n".join(head + body) + "\n"
    for s in TAB_ORDER:
        cells = [("-" + str(p.fret).ljust(COL - 1, "-")) if p.string == s else "-" * COL for p in item.positions]
        line = _spaced(cells, sep).replace(" ", "-")
        body.append(f"{s}  |{line}|")
    body.append("")
    fing = [" " + str(p.finger) for p in item.positions]
    body.append("LH  " + _spaced(fing, sep) + "   (left-hand finger, 0 = open string)")
    if item.composition:
        al = _letters(vs.aligned_composition())
        mi = _letters(item.composition)
        body.append("Ma  " + _spaced([" " + x for x in al], sep) + f"  aligned motor chunks {vs.comp_to_str(vs.aligned_composition())}")
        body.append("Mm  " + _spaced([" " + x for x in mi], sep) +
                    f"  misaligned motor chunks {vs.comp_to_str(item.composition)}")
    return "\n".join(head + body) + "\n"


# ---------------------------------------------------------------------------
# MIDI
# ---------------------------------------------------------------------------

def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def build_midi(item: Item) -> bytes:
    ppq = config.MIDI_PPQ
    tempo = round(60_000_000 / config.BPM)
    track = bytearray()
    track += _vlq(0) + b"\xff\x03" + _vlq(len(item.item_id)) + item.item_id.encode()
    track += _vlq(0) + b"\xff\x51\x03" + tempo.to_bytes(3, "big")
    track += _vlq(0) + b"\xff\x58\x04" + bytes([config.BEATS_PER_BAR, 2, 24, 8])
    track += _vlq(0) + bytes([0xC0, config.MIDI_PROGRAM])
    events = []
    gate = int(round(ppq * config.NOTE_GATE))
    for i, pitch in enumerate(item.pitches):
        vel = item.velocities[i] if item.velocities else config.MIDI_VELOCITY
        start = i * ppq
        events.append((start, 1, bytes([0x90, pitch, vel])))
        events.append((start + gate, 0, bytes([0x80, pitch, 0])))
    events.sort(key=lambda e: (e[0], e[1]))
    t = 0
    for tick, _, msg in events:
        track += _vlq(tick - t) + msg
        t = tick
    end = config.N_NOTES * ppq
    track += _vlq(max(end - t, 0)) + b"\xff\x2f\x00"
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def export_items(items: Sequence[Item], outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    tabs = []
    for it in items:
        t = tab_item(it)
        tabs.append(t)
        open(os.path.join(outdir, f"{it.item_id}.txt"), "w").write(t)
        open(os.path.join(outdir, f"{it.item_id}.mid"), "wb").write(build_midi(it))
    open(os.path.join(outdir, "all_tabs.txt"), "w").write("\n".join(tabs))
