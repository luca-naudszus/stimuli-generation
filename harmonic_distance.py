"""
harmonic_distance.py
=============================

"""

import itertools
from typing import Dict, List, Tuple
from ukulele_geometry import OPEN_STRING_MIDI


def minimal_voice_leading_distance(pcs_a: Tuple[int, ...], pcs_b: Tuple[int, ...]) -> float:
    """Octave-independent, permutation-optimized circular key class distance (Tymoczko style)."""
    def circ_dist(a: int, b: int) -> int:
        d = abs(a - b) % 12
        return min(d, 12 - d)

    best = None
    for perm in itertools.permutations(pcs_b):
        # Works only for tritones, not for more complex chords (due to zip)
        total = sum(circ_dist(a, b) for a, b in zip(pcs_a, perm))
        if best is None or total < best:
            best = total
    return float(best)

### Currently without use
# GENERATION
def chord_sounding_midi(chord_shape: Dict[str, int]) -> List[int]:
    """Actually sounding (MIDI) tones of a chord."""
    return sorted(OPEN_STRING_MIDI[s] + f for s, f in chord_shape.items())