"""
chord_difficulty.py
=============================
Old chord difficulty code (from legacy/), kept for the chord strand (build spec section 11). NOT used by the melody
pipeline. A chord shape is a dict string -> fret, e.g. {"G": 0, "C": 0, "E": 0, "A": 3} for C major (0003).

Two measures, both as transparent raw components rather than one opaque number, so they can be checked against
pilot data:
  chord_difficulty           one chord on its own: fret span (mm), fingers needed, barre
  chord_transition_distance  moving from chord A to chord B: hand shift, finger travel, barre change
"""

from dataclasses import dataclass
from typing import Dict
from ukustim.core.ukulele_geometry import fret_position_mm, DEFAULT_SCALE_LENGTH_MM

# weights of the chord difficulty score: per mm of span, per finger, for a barre (draft values)
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
    """Heuristic: 3 or more strings pressed at the same (non-open) fret -> barre.
    Caveat: this also marks D (2-2-2-0) as a barre, although it is usually played with three separate fingers;
    tighten before real use (e.g. also require fret >= 3)."""
    frets = [f for f in chord_shape.values() if f > 0]
    if not frets:
        return False
    most_common_count = max(frets.count(f) for f in set(frets))
    return most_common_count >= 3


def chord_span_mm(chord_shape: Dict[str, int], scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physical stretch of the fretting hand (mm) between the lowest and the highest pressed (non-open) fret."""
    fretted = [f for f in chord_shape.values() if f > 0]
    if not fretted:
        return 0.0
    positions = [fret_position_mm(f, scale_length_mm) for f in fretted]
    return max(positions) - min(positions)


def num_fingers_required(chord_shape: Dict[str, int]) -> int:
    """Rough estimate of the fingers needed (a barre counts as one finger)."""
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
    """Difficulty of one chord shape on its own (independent of transitions): weighted sum of span (mm), number of
    fingers and barre, returned together with the raw components so the weights can be edited and validated
    against pilot data."""
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
    """Physical distance of a chord change, after the along / across decomposition of the Fretting-Transformer paper
    (difficulty = fret stretch + locality + vertical stretch):
      hand_shift_mm       movement of the centre of the pressed frets along the neck
      finger_movement_mm  summed movement of each string's fret along the neck (open string = position 0)
      barre_change        a barre is added or released (fixed penalty in mm)
    A candidate for the 'change cost' of the chord neutrality rule (build spec section 11)."""
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

