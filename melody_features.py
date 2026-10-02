"""
melody_features.py
=============================
Aggregates physical and musical features of a melody into one flat dict -
the melody counterpart to progression_features.py.
"""

from typing import Dict, Optional, Sequence, Set
from ukulele_geometry import DEFAULT_SCALE_LENGTH_MM
from melody_difficulty import melody_physical_features
from melody_intervals import melody_interval_features


def melody_features(
    midi_sequence: Sequence[int],
    key_pcs: Optional[Set[int]] = None,
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    leap_threshold: int = 3,
) -> Dict[str, float]:
    """Physical (mm on the fretboard) + musical (semitones, contour) features.
    Keys of the two parts do not overlap, so the dicts are simply merged."""
    midi_sequence = [int(p) for p in midi_sequence]
    physical = melody_physical_features(midi_sequence, scale_length_mm)
    musical = melody_interval_features(midi_sequence, key_pcs, leap_threshold)
    return {**physical, **musical}