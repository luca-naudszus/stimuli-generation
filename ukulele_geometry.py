"""
ukulele_geometry.py
=============================

"""
import math
from typing import Dict, Tuple

STRING_ORDER: Tuple[str, str, str, str] = ("G", "C", "E", "A")
OPEN_STRING_MIDI: Dict[str, int] = {"G": 67, "C": 60, "E": 64, "A": 69}
STRING_SPACING_MM: float = 11.0

SCALE_LENGTHS_MM = {"soprano": 340.0, "concert": 380.0, "tenor": 430.0}
DEFAULT_SCALE_LENGTH_MM = SCALE_LENGTHS_MM["soprano"]


def fret_position_mm(fret: int, scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physical distance of a fret from the nut, using the
    "Rule of 18": D(n) = scale_length * (1 - 2^(-n/12)). fret=0 -> 0.0."""
    if fret <= 0:
        return 0.0
    return scale_length_mm * (1 - 2 ** (-fret / 12))


def fretboard_euclidean_mm(
    pos_a: Tuple[str, int],
    pos_b: Tuple[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
) -> float:
    """Euclidean physical distance between two [string, fret]-positions:
    "along" (non linear fret distance) + "across"
    (linear string distance)."""
    str_a, fret_a = pos_a
    str_b, fret_b = pos_b
    dx = fret_position_mm(fret_b, scale_length_mm) - fret_position_mm(fret_a, scale_length_mm)
    dy = (STRING_ORDER.index(str_b) - STRING_ORDER.index(str_a)) * STRING_SPACING_MM
    return math.hypot(dx, dy)