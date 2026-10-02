"""
melody_intervals.py
=============================
Musical (pitch-based) features of a melody. Needs only MIDI numbers,
no fingering and no instrument geometry - the melodic counterpart
to harmonic_distance.py.
"""
#TODO: Add expectancy

from typing import Dict, List, Optional, Sequence, Set


def melodic_intervals(midi_sequence: Sequence[int]) -> List[int]:
    """Signed intervals in semitones between consecutive tones."""
    return [b - a for a, b in zip(midi_sequence, midi_sequence[1:])]


def count_direction_changes(intervals: Sequence[int]) -> int:
    """Number of changes between rising and falling motion.
    Repeated tones (interval 0) are ignored, not counted as a change."""
    signs = [1 if i > 0 else -1 for i in intervals if i != 0]
    return sum(1 for a, b in zip(signs, signs[1:]) if a != b)


def melody_interval_features(
    midi_sequence: Sequence[int],
    key_pcs: Optional[Set[int]] = None,
    leap_threshold: int = 3,
) -> Dict[str, float]:
    """Interval, range, contour and pitch-class features.

    key_pcs: optional set of pitch classes of the key (e.g. {0,2,4,5,7,9,11}
    for C major). If given, `out_of_key_ratio` is added.
    leap_threshold: smallest absolute interval (semitones) counted as a leap.
    """
    if not midi_sequence:
        raise ValueError("Empty melody.")

    ivs = melodic_intervals(midi_sequence)
    abs_ivs = [abs(i) for i in ivs]
    n_steps = max(len(ivs), 1)
    pcs = [p % 12 for p in midi_sequence]

    feats = dict(
        mean_interval_semitones=sum(abs_ivs) / n_steps,
        max_interval_semitones=float(max(abs_ivs, default=0)),
        leap_ratio=sum(1 for a in abs_ivs if a >= leap_threshold) / n_steps,
        step_ratio=sum(1 for a in abs_ivs if 1 <= a <= 2) / n_steps,
        repeat_ratio=sum(1 for a in abs_ivs if a == 0) / n_steps,
        ambitus_semitones=float(max(midi_sequence) - min(midi_sequence)),
        direction_changes=float(count_direction_changes(ivs)),
        n_pitch_classes=float(len(set(pcs))),
    )
    if key_pcs is not None:
        feats["out_of_key_ratio"] = sum(1 for p in pcs if p not in key_pcs) / len(pcs)
    return feats