"""
string_shift.py
=============================
String-pair shift (build spec section 5): the same movement (frets, fingers, relative string pattern) on
another pair of strings. Pitches, intervals and contour change.

Every note moves by the same string step, so string crossings stay at the same transitions (neutrality is kept
without a new check) and the left-hand ('lh') motor chunks are those of the base. Because the G string is tuned high
(re-entrant), a note moved between the G and C strings changes pitch in the opposite direction from the others
(C->E +4, E->A +5, but G->C -7), which can produce large jumps. The shifted melody is usually out of key and its
musical chunks are 'new:' (never trained).
"""

from typing import Optional

from ukustim.core import fretboard as fb
from ukustim.core.fretboard import Pos
from ukustim.core.items import Item, item_from_positions
from ukustim.core.ukulele_geometry import STRING_ORDER


def string_pair_shift(base: Item, direction: Optional[str] = None) -> Optional[Item]:
    """Move the whole strings-and-frets pattern one string set: 'down' (C-E-A -> G-C-E, strings move
    one place towards G) or 'up' (G-C-E -> C-E-A). direction=None tries 'down', then 'up'.
    Returns None if neither works (only possible if the base spans more than 3 strings, which the base rules forbid)."""
    for d in ([direction] if direction else ["down", "up"]):
        delta = -1 if d == "down" else 1
        new = []
        ok = True
        for p in base.positions:
            j = fb.string_index(p.string) + delta
            if not 0 <= j < len(STRING_ORDER):     # would fall off the neck (below G or above A)
                ok = False
                break
            new.append(Pos(STRING_ORDER[j], p.fret, p.finger))   # same fret and finger, neighbouring string
        if not ok:
            continue
        return item_from_positions(f"{base.item_id}-shift", base.family_id, "family", "string-pair shift", new,
                                   base.composition, base.item_id, key=base.key, meta={"direction": d})
    return None
