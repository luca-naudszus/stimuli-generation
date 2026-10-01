"""
harmonic_distance.py
=============================

"""

import itertools
from typing import Dict, List, Tuple
from ukulele_geometry import OPEN_STRING_MIDI


def minimal_voice_leading_distance(pcs_a: Tuple[int, ...], pcs_b: Tuple[int, ...]) -> float:
    """Oktavunabhaengige, permutationsoptimierte zirkulaere Tonklassen-
    Distanz (Tymoczko-Stil) - die 'freie Umkehrungssuche', die in der
    Original-Pipeline-Notiz als fehlender Schritt vermerkt war."""
    def circ_dist(a: int, b: int) -> int:
        d = abs(a - b) % 12
        return min(d, 12 - d)

    best = None
    for perm in itertools.permutations(pcs_b):
        total = sum(circ_dist(a, b) for a, b in zip(pcs_a, perm))
        if best is None or total < best:
            best = total
    return float(best)


def chord_sounding_midi(chord_shape: Dict[str, int]) -> List[int]:
    """Tatsaechlich klingende MIDI-Toene eines Griffs."""
    return sorted(OPEN_STRING_MIDI[s] + f for s, f in chord_shape.items())