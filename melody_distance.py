"""
melody_distance.py
=============================

"""

from typing import Dict, List, Optional, Sequence, Tuple
from ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI, DEFAULT_SCALE_LENGTH_MM, fretboard_euclidean_mm


def pitch_to_positions(midi_pitch: int, max_fret: int = 12) -> List[Tuple[str, int]]:
    """All playable [string, fret]-positions for a MIDI tone."""
    out = []
    for s in STRING_ORDER:
        fret = midi_pitch - OPEN_STRING_MIDI[s]
        if 0 <= fret <= max_fret:
            out.append((s, fret))
    return out


def assign_fret_path(
    midi_sequence: Sequence[int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    max_fret: int = 12,
) -> List[Tuple[str, int]]:
    """Greedy minimized physical distance to the previous fret position.
    For short beginner melodies (6-10 tones) sufficient.
    For longer or more complex melodies a DP approach (Sayegh, 1989) would be more precise.
    Only used as a fallback when no explicit path is given."""
    path: List[Tuple[str, int]] = []
    prev: Optional[Tuple[str, int]] = None
    for pitch in midi_sequence:
        candidates = pitch_to_positions(pitch, max_fret)
        if not candidates:
            raise ValueError(f"MIDI-Ton {pitch} auf keiner Saite innerhalb {max_fret} Buenden greifbar.")
        if prev is None:
            chosen = min(candidates, key=lambda p: p[1])
        else:
            chosen = min(candidates, key=lambda p: fretboard_euclidean_mm(prev, p, scale_length_mm))
        path.append(chosen)
        prev = chosen
    return path


def melody_physical_features(
    midi_sequence: Sequence[int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    path: Optional[Sequence[Tuple[str, int]]] = None,
) -> Dict[str, float]:
    """Physical distance features for a melody, analogous to the physical part of
    `progression_features`. `path` = explicit (string, fret) position per tone;
    if None, the greedy fingering `assign_fret_path` is used."""
    if path is None:
        path = assign_fret_path(midi_sequence, scale_length_mm)
    elif len(path) != len(midi_sequence):
        raise ValueError("path and midi_sequence must have the same length.")
    steps = [fretboard_euclidean_mm(path[i], path[i + 1], scale_length_mm) for i in range(len(path) - 1)]
    n_steps = max(len(steps), 1)
    open_string_ratio = sum(1 for _, f in path if f == 0) / len(path)
    return dict(
        mean_step_distance_mm=sum(steps) / n_steps,
        max_step_distance_mm=max(steps, default=0.0),
        total_path_distance_mm=sum(steps),
        open_string_ratio=open_string_ratio,
    )