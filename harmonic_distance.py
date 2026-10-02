"""
harmonic_distance.py
=============================

"""

import itertools
from typing import Dict, List, Tuple
from ukulele_geometry import OPEN_STRING_MIDI

def _circ_dist(a: int, b: int) -> int:
    """Circular distance between two pitch classes (0..6)."""
    d = abs(a - b) % 12
    return min(d, 12 - d)

def minimal_voice_leading_distance(pcs_a: Tuple[int, ...], pcs_b: Tuple[int, ...]) -> float:
    """Octave-independent, assignment-optimized circular pitch class distance (Tymoczko style)."""
    if not pcs_a or not pcs_b:
        raise ValueError("Pitch class sets must not be empty.")
    small, large = sorted((pcs_a, pcs_b), key=len)
 
    best = None
    for assignment in itertools.product(small, repeat=len(large)):
        if len(set(assignment)) < len(small):  # every note of the smaller chord must be used
            continue
        total = sum(_circ_dist(l, s) for l, s in zip(large, assignment))
        if best is None or total < best:
            best = total
    return float(best)

def common_tone_ratio(pcs_a: Tuple[int, ...], pcs_b: Tuple[int, ...]) -> float:
    """Shared pitch classes divided by the size of the larger chord (0..1).
    C -> Am: 2/3, C -> F: 1/3, C -> F#: 0."""
    return len(set(pcs_a) & set(pcs_b)) / max(len(pcs_a), len(pcs_b))
 
 
def root_motion_fifths(root_a: int, root_b: int) -> int:
    """Distance between two roots on the circle of fifths (0..6).
    C -> G: 1, C -> F: 1, C -> D: 2, C -> F#: 6."""
    return _circ_dist((root_a * 7) % 12, (root_b * 7) % 12)


### Currently without use
# GENERATION
def chord_sounding_midi(chord_shape: Dict[str, int]) -> List[int]:
    """Actually sounding (MIDI) tones of a chord."""
    return sorted(OPEN_STRING_MIDI[s] + f for s, f in chord_shape.items())