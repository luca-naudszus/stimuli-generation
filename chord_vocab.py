"""
chord_vocab.py
=============================

"""

from typing import Dict, Tuple
from ukulele_geometry import OPEN_STRING_MIDI

# contains only #, no b
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# currently not used
# GENERATION
CHORD_QUALITY_INTERVALS: Dict[str, Tuple[int, int, int]] = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "dim":   (0, 3, 6),
}

MAJOR_SCALE_STEPS = [0, 2, 4, 5, 7, 9, 11]
DEGREE_QUALITIES = ["major", "minor", "minor", "major", "major", "minor", "dim"]
DEGREE_LABELS = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]

# Standard key set. 
DEFAULT_KEY_ROOTS: Dict[str, int] = {"C": 0, "G": 7, "D": 2, "A": 9, "F": 5}

# currently not used
def chord_label(root_pc: int, quality: str) -> str:
    name = NOTE_NAMES[root_pc % 12]
    if quality == "major":
        return name
    if quality == "minor":
        return name + "m"
    if quality == "dim":
        return name + "dim"
    raise ValueError(quality)

# currently not used
def diatonic_progression_labels(key_name: str, key_roots: Dict[str, int] = DEFAULT_KEY_ROOTS) -> Dict[str, str]:
    """Translates Roman numeral progressions into chord labels."""
    root = key_roots[key_name]
    out = {}
    for step, quality, degree_label in zip(MAJOR_SCALE_STEPS, DEGREE_QUALITIES, DEGREE_LABELS):
        chord_root = (root + step) % 12
        out[degree_label] = chord_label(chord_root, quality)
    return out

# Defined chords
CHORD_SHAPES: Dict[str, Dict[str, int]] = {
    "C":  {"G": 0, "C": 0, "E": 0, "A": 3},
    "G":  {"G": 0, "C": 2, "E": 3, "A": 2},
    "F":  {"G": 2, "C": 0, "E": 1, "A": 0},
    "Am": {"G": 2, "C": 0, "E": 0, "A": 0},
    "Dm": {"G": 2, "C": 2, "E": 1, "A": 0},
    "Em": {"G": 0, "C": 4, "E": 0, "A": 2},
    "E": {"G": 1, "C": 4, "E": 0, "A": 2},
    # ...
    # Format: {"G": fret, "C": fret, "E": fret, "A": fret}
}

def pitch_classes_from_shape(chord_shape: Dict[str, int]) -> Tuple[int, ...]:
    """Translates chord shapes into pitch classes."""
    return tuple(sorted({(OPEN_STRING_MIDI[s] + f) % 12 for s, f in chord_shape.items()}))

CHORD_VOCAB: Dict[str, Dict] = {
    label: dict(shape=shape, pitch_classes=pitch_classes_from_shape(shape))
    for label, shape in CHORD_SHAPES.items()
}

# currently not in use
PROGRESSION_KEYS: Dict[str, Dict[str, str]] = {
    key_name: diatonic_progression_labels(key_name) for key_name in DEFAULT_KEY_ROOTS
}