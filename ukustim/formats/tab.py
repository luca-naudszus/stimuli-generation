"""
tab.py
=============================
ASCII tab for researchers: left-hand fingers, musical chunk markers (|) and the aligned / misaligned motor-chunk
rows. Not a participant cue (see cues.py): the markers would act as grouping cues.

Layout of one tab (4 characters per note, '|' after every musical chunk):
    pitch names
    A |--- ... |      one line per string, top line = A string (standard ukulele tab), fret number where played
    E |...
    C |...
    G |...
    LH   left-hand finger per note
    Ma   aligned motor chunks (a letter per chunk: A A A B B B ...)
    Mm   misaligned motor chunks (letters change at each motor boundary)
"""

from typing import List, Sequence

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core import versions as vs
from ukustim.core.items import Item

TAB_ORDER = ("A", "E", "C", "G")    # ukulele tab: top line = A string
COL = 4                             # characters per note column


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
    """The researcher tab of one item (see module docstring). Listen-only items get pitch names (and velocities for
    the accent probe) instead of string lines."""
    n = config.CHUNK_LEN
    sep = {n * k - 1 for k in range(1, config.N_CHUNKS)}     # 0-based notes after which a '|' is drawn (2, 5, 8)
    head = [f"{item.item_id}  ({item.variant_type}; family {item.family_id}; layer {item.layer})",
            f"Key {item.key or 'chromatic'}, {config.BPM} bpm, {config.BEATS_PER_BAR}/4, one note per beat "
            f"(1 chunk = 1 bar = {60 * n / config.BPM:g} s, item = {60 * config.N_NOTES / config.BPM:g} s)",
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
