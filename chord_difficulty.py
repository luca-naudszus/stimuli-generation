"""
chord_difficulty.py
=============================

"""

from dataclasses import dataclass
from typing import Dict
from ukulele_geometry import fret_position_mm, DEFAULT_SCALE_LENGTH_MM

DEFAULT_WEIGHTS = dict(span=1.0, fingers=3.0, barre=8.0)

@dataclass
class ChordDifficulty:
    span_mm: float
    num_fingers: int
    barre: bool
    score: float

@dataclass
class TransitionDistance:
    hand_shift_mm: float
    finger_movement_mm: float
    barre_change: bool
    total_mm: float


def is_barre(chord_shape: Dict[str, int]) -> bool:
    """Defines chords with 3+ strings at the same non-empty fret as Barré. 
    Not 100% true, e.g. D major."""
    frets = [f for f in chord_shape.values() if f > 0]
    if not frets:
        return False
    most_common_count = max(frets.count(f) for f in set(frets))
    return most_common_count >= 3


def chord_span_mm(chord_shape: Dict[str, int], scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physical chord span (mm) between lowest and highest played fret."""
    fretted = [f for f in chord_shape.values() if f > 0]
    if not fretted:
        return 0.0
    positions = [fret_position_mm(f, scale_length_mm) for f in fretted]
    return max(positions) - min(positions)


def num_fingers_required(chord_shape: Dict[str, int]) -> int:
    """Rough estimation of number of required fingers."""
    fretted = [f for f in chord_shape.values() if f > 0]
    if not fretted:
        return 0
    if is_barre(chord_shape):
        barre_fret = max(set(fretted), key=fretted.count)
        other_frets = {f for f in fretted if f != barre_fret}
        return 1 + len(other_frets)
    return len(set(fretted)) if len(set(fretted)) == len(fretted) else len(fretted)


def chord_difficulty(
    chord_shape: Dict[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    weights: Dict[str, float] = None,
) -> ChordDifficulty:
    """Difficulty of single chords, independent of transitions."""
    weights = weights or DEFAULT_WEIGHTS
    span = chord_span_mm(chord_shape, scale_length_mm)
    fingers = num_fingers_required(chord_shape)
    barre = is_barre(chord_shape)
    score = weights["span"] * span + weights["fingers"] * fingers + weights["barre"] * barre
    return ChordDifficulty(span_mm=span, num_fingers=fingers, barre=barre, score=score)





def chord_transition_distance(
    chord_a: Dict[str, int],
    chord_b: Dict[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    barre_change_penalty_mm: float = 15.0,
) -> TransitionDistance:
    """Physische Uebergangsdistanz, angelehnt an die along/across-Zerlegung
    aus dem Fretting-Transformer-Paper (difficulty = fret_stretch +
    locality + vertical_stretch)."""
    all_strings = set(chord_a) | set(chord_b)

    def centroid(shape: Dict[str, int]) -> float:
        fretted = [f for f in shape.values() if f > 0]
        if not fretted:
            return 0.0
        return sum(fret_position_mm(f, scale_length_mm) for f in fretted) / len(fretted)

    hand_shift = abs(centroid(chord_b) - centroid(chord_a))

    finger_movement = 0.0
    for s in all_strings:
        fa, fb = chord_a.get(s, 0), chord_b.get(s, 0)
        finger_movement += abs(fret_position_mm(fb, scale_length_mm) - fret_position_mm(fa, scale_length_mm))

    barre_change = is_barre(chord_a) != is_barre(chord_b)
    penalty = barre_change_penalty_mm if barre_change else 0.0
    total = hand_shift + finger_movement + penalty
    return TransitionDistance(hand_shift_mm=hand_shift, finger_movement_mm=finger_movement,
                               barre_change=barre_change, total_mm=total)

