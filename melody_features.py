"""
melody_features.py
=============================
Aggregates physical and musical features of a melody into one flat dict -
the melody counterpart to progression_features.py.
"""

from typing import Dict, Optional, Sequence, Set, Tuple
from ukulele_geometry import DEFAULT_SCALE_LENGTH_MM
from music_theory import best_key_fit
from melody_distance import melody_physical_features
from melody_intervals import melody_interval_features


def melody_features(
    midi_sequence: Sequence[int],
    key_pcs: Optional[Set[int]] = None,
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    leap_threshold: int = 3,
    path: Optional[Sequence[Tuple[str, int]]] = None,
) -> Dict[str, float]:
    """Physical (mm on the fretboard) + musical (semitones, contour) features.

    key_pcs: pitch classes of a fixed key. If None, the best fitting of all
    12 major keys is used, so `out_of_key_ratio` is always present.
    path: explicit (string, fret) per tone; None = greedy fingering."""
    midi_sequence = [int(p) for p in midi_sequence]
    if key_pcs is None:
        from music_theory import major_scale_pcs
        key_name, _ = best_key_fit([{p % 12} for p in midi_sequence])
        key_pcs = major_scale_pcs(key_name)
    physical = melody_physical_features(midi_sequence, scale_length_mm, path)
    musical = melody_interval_features(midi_sequence, key_pcs, leap_threshold)
    return {**physical, **musical}