"""
ukulele_geometry.py
=============================
Physical facts about the instrument: string order, open-string pitches, string spacing and fret positions.

- Strings are listed in their physical order across the neck: G, C, E, A. The tuning is re-entrant: the G string is
  tuned to G4 (above C4), so moving from the C string to the G string goes UP a fifth, not down a fourth.
  This matters for the string-pair shift (family/string_shift.py), which moves a pattern to the neighbouring strings.
- Distances (mm) feed the difficulty metric (analysis/difficulty.py): how far the left hand travels between notes.
"""
import math
from typing import Dict, Tuple

# Physical order across the neck (index 0 = G ... 3 = A). String index differences = string changes.
STRING_ORDER: Tuple[str, str, str, str] = ("G", "C", "E", "A")
# Open-string pitches (MIDI), standard re-entrant tuning G4 C4 E4 A4.
OPEN_STRING_MIDI: Dict[str, int] = {"G": 67, "C": 60, "E": 64, "A": 69}
# Distance between neighbouring strings at the frets (approximate, soprano ukulele).
STRING_SPACING_MM: float = 11.0

SCALE_LENGTHS_MM = {"soprano": 340.0, "concert": 380.0, "tenor": 430.0}
DEFAULT_SCALE_LENGTH_MM = SCALE_LENGTHS_MM["soprano"]


def fret_position_mm(fret: int, scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physical distance of a fret from the nut (equal temperament):
    D(n) = scale_length * (1 - 2^(-n/12)). fret = 0 (open string) -> 0.0.
    The frets get closer together further up the neck, so the same number of frets is a shorter stretch there."""
    if fret <= 0:
        return 0.0
    return scale_length_mm * (1 - 2 ** (-fret / 12))


def fretboard_euclidean_mm(
    pos_a: Tuple[str, int],
    pos_b: Tuple[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
) -> float:
    """Straight-line physical distance between two (string, fret) positions:
    'along' the neck (non-linear fret distance) combined with 'across' it (linear string spacing)."""
    str_a, fret_a = pos_a
    str_b, fret_b = pos_b
    dx = fret_position_mm(fret_b, scale_length_mm) - fret_position_mm(fret_a, scale_length_mm)   # along the neck
    dy = (STRING_ORDER.index(str_b) - STRING_ORDER.index(str_a)) * STRING_SPACING_MM             # across the neck
    return math.hypot(dx, dy)
