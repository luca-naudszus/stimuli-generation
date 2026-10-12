"""
chord_vocab.py
=============================
Chord data. Every chord label has one or more variations (ways to play it).
CHORD_SHAPES: label -> list of shapes; variation k is called e.g. 'Am (Var. 2)'.
"""

from typing import Dict, List, Tuple
from ukulele_geometry import OPEN_STRING_MIDI
from music_theory import NOTE_NAMES, MAJOR_SCALE_STEPS, variant_id

CHORD_QUALITY_INTERVALS: Dict[str, Tuple[int, int, int]] = {
    "major": (0, 4, 7),
    "minor": (0, 3, 7),
    "dim":   (0, 3, 6),
}

DEGREE_QUALITIES = ["major", "minor", "minor", "major", "major", "minor", "dim"]
DEGREE_LABELS = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]

# Standard key set.
DEFAULT_KEY_ROOTS: Dict[str, int] = {"C": 0, "G": 7, "D": 2, "A": 9, "F": 5}


def root_pc_from_label(label: str) -> int:
    """Root pitch class of a chord label ('C' -> 0, 'F#m' -> 6, 'Bb' -> 10, 'Bdim' -> 11)."""
    pc = NOTE_NAMES.index(label[0])
    if len(label) > 1 and label[1] == "#":
        pc += 1
    elif len(label) > 1 and label[1] == "b":
        pc -= 1
    return pc % 12


def quality_from_label(label: str) -> str:
    if label.endswith("dim"):
        return "dim"
    if label.endswith("m"):
        return "minor"
    return "major"


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


# ---------------------------------------------------------------------------
# Defined chords: label -> list of variations (first entry = Var. 1)
# Format of one shape: {"G": fret, "C": fret, "E": fret, "A": fret}
# ---------------------------------------------------------------------------
CHORD_SHAPES: Dict[str, List[Dict[str, int]]] = {
    "C":  [{"G": 0, "C": 0, "E": 0, "A": 3},
           {"G": 5, "C": 4, "E": 3, "A": 3}],
    "G":  [{"G": 0, "C": 2, "E": 3, "A": 2}],
    "F":  [{"G": 2, "C": 0, "E": 1, "A": 0},
           {"G": 5, "C": 5, "E": 5, "A": 3}],
    "Am": [{"G": 2, "C": 0, "E": 0, "A": 0},
           {"G": 2, "C": 0, "E": 0, "A": 3}],
    "Dm": [{"G": 2, "C": 2, "E": 1, "A": 0},
           {"G": 7, "C": 5, "E": 5, "A": 5}],
    "Em": [{"G": 0, "C": 4, "E": 0, "A": 2},
           {"G": 0, "C": 4, "E": 3, "A": 2}],
    "E":  [{"G": 1, "C": 4, "E": 0, "A": 2},
           {"G": 4, "C": 4, "E": 4, "A": 2}],
    "D":  [{"G": 2, "C": 2, "E": 2, "A": 0},
           {"G": 7, "C": 6, "E": 5, "A": 5}],
    "A":  [{"G": 2, "C": 1, "E": 0, "A": 0},
           {"G": 2, "C": 4, "E": 5, "A": 4}],
    "Bdim":  [{"G": 4, "C": 2, "E": 1, "A": 2}],
    "F#dim": [{"G": 2, "C": 0, "E": 2, "A": 0}],
}


def pitch_classes_from_shape(chord_shape: Dict[str, int]) -> Tuple[int, ...]:
    """Translates chord shapes into pitch classes."""
    return tuple(sorted({(OPEN_STRING_MIDI[s] + f) % 12 for s, f in chord_shape.items()}))


# variant ID -> data; label -> list of variant IDs
CHORD_VOCAB: Dict[str, Dict] = {}
CHORD_VARIANTS: Dict[str, List[str]] = {}
for _label, _shapes in CHORD_SHAPES.items():
    _ids = []
    for _k, _shape in enumerate(_shapes, start=1):
        _vid = variant_id(_label, _k)
        CHORD_VOCAB[_vid] = dict(
            shape=_shape,
            pitch_classes=pitch_classes_from_shape(_shape),
            label=_label,
            variant=_k,
            root_pc=root_pc_from_label(_label),
        )
        _ids.append(_vid)
    CHORD_VARIANTS[_label] = _ids


def validate_chord_shapes(vocab: Dict[str, Dict] = None) -> None:
    """Checks that every variation really sounds the chord its label promises
    (pitch classes of the shape == root + quality intervals). Raises ValueError."""
    vocab = vocab or CHORD_VOCAB
    errors = []
    for vid, entry in vocab.items():
        label = entry["label"]
        expected = tuple(sorted((entry["root_pc"] + iv) % 12
                                for iv in CHORD_QUALITY_INTERVALS[quality_from_label(label)]))
        if entry["pitch_classes"] != expected:
            errors.append(f"{vid}: pitch classes {entry['pitch_classes']} != expected {expected}")
    if errors:
        raise ValueError("Inconsistent chord shapes:\n  " + "\n  ".join(errors))


# currently not in use
PROGRESSION_KEYS: Dict[str, Dict[str, str]] = {
    key_name: diatonic_progression_labels(key_name) for key_name in DEFAULT_KEY_ROOTS
}