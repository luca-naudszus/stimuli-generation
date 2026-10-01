"""
melody_distance.py
=============================

"""

from typing import Dict, List, Optional, Sequence, Tuple
from ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI, DEFAULT_SCALE_LENGTH_MM, fretboard_euclidean_mm

def pitch_to_positions(midi_pitch: int, max_fret: int = 12) -> List[Tuple[str, int]]:
    """Alle spielbaren (Saite, Bund)-Positionen fuer eine MIDI-Tonhoehe."""
    out = []
    for s in STRING_ORDER:
        fret = midi_pitch - OPEN_STRING_MIDI[s]
        if 0 <= fret <= max_fret:
            out.append((s, fret))
    return out


def assign_fingering_path(
    midi_sequence: Sequence[int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    max_fret: int = 12,
) -> List[Tuple[str, int]]:
    """Greedy-Fingersatzwahl: minimiert physische Distanz zur jeweils
    vorherigen Position. Fuer kurze Anfaenger-Melodien (6-10 Toene)
    ausreichend; fuer laengere/komplexere Melodien waere ein DP-Ansatz
    a la Sayegh (1989) praeziser."""
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
) -> Dict[str, float]:
    """Physische Distanz-Features fuer eine Melodie, analog zu
    `progression_physical_features` fuer Akkorde."""
    path = assign_fingering_path(midi_sequence, scale_length_mm)
    steps = [fretboard_euclidean_mm(path[i], path[i + 1], scale_length_mm) for i in range(len(path) - 1)]
    n_steps = max(len(steps), 1)
    open_string_ratio = sum(1 for _, f in path if f == 0) / len(path)
    return dict(
        mean_step_distance_mm=sum(steps) / n_steps,
        max_step_distance_mm=max(steps, default=0.0),
        total_path_distance_mm=sum(steps),
        open_string_ratio=open_string_ratio,
    )