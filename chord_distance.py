"""
chord_distance.py
=============================

"""

from __future__ import annotations
import itertools
from typing import Dict, List, Sequence, Tuple

from ukulele_geometry import fretboard_euclidean_mm, DEFAULT_SCALE_LENGTH_MM, OPEN_STRING_MIDI
from chord_difficulty import chord_difficulty, chord_transition_distance
from harmonic_distance import minimal_voice_leading_distance
from melody_distance import melody_physical_features

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def midi_from_object(obj) -> int:
    """Duck typing adapter for raw int MIDI numbers or music21 objects."""
    if isinstance(obj, int):
        return obj
    if hasattr(obj, "pitch") and hasattr(obj.pitch, "midi"):
        return int(obj.pitch.midi)
    if hasattr(obj, "midi"):
        return int(obj.midi)
    return int(obj)

def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    return cov / (sx * sy)


# ---------------------------------------------------------------------------
# Chord vocabulary
# ---------------------------------------------------------------------------

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

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

def chord_label(root_pc: int, quality: str) -> str:
    name = NOTE_NAMES[root_pc % 12]
    if quality == "major":
        return name
    if quality == "minor":
        return name + "m"
    if quality == "dim":
        return name + "dim"
    raise ValueError(quality)

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
    return tuple(sorted({(OPEN_STRING_MIDI[s] + f) % 12 for s, f in chord_shape.items()}))

CHORD_VOCAB: Dict[str, Dict] = {
    label: dict(shape=shape, pitch_classes=pitch_classes_from_shape(shape), occurs_in=[])
    for label, shape in CHORD_SHAPES.items()
}
PROGRESSION_KEYS: Dict[str, Dict[str, str]] = {
    key_name: diatonic_progression_labels(key_name) for key_name in DEFAULT_KEY_ROOTS
}

# ---------------------------------------------------------------------------
# aggregated features for one chord progression
# ---------------------------------------------------------------------------

def progression_physical_features(
    chord_labels: Sequence[str],
    vocab: Dict[str, Dict] = None,
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
) -> Dict[str, float]:
    """Aggregiert Einzelgriff- und Uebergangsschwierigkeit (physisch) sowie
    die minimale Voice-Leading-Distanz (harmonisch) einer Akkordfolge zu
    einem flachen Feature-Dict - kompatibel mit der bestehenden
    `matched_split`-Funktion aus der Original-Pipeline."""
    vocab = vocab or CHORD_VOCAB
    missing = [c for c in chord_labels if vocab.get(c, {}).get("shape") is None]
    if missing:
        raise ValueError(f"Keine offene Griffposition bekannt fuer: {missing}")

    shapes = [vocab[c]["shape"] for c in chord_labels]
    pcs_list = [vocab[c]["pitch_classes"] for c in chord_labels]

    chord_scores = [chord_difficulty(s, scale_length_mm) for s in shapes]
    transitions = [chord_transition_distance(shapes[i], shapes[i + 1], scale_length_mm)
                   for i in range(len(shapes) - 1)]
    harmonic = [minimal_voice_leading_distance(pcs_list[i], pcs_list[i + 1])
                for i in range(len(pcs_list) - 1)]

    n_chords = len(shapes)
    n_trans = max(len(transitions), 1)

    return dict(
        mean_chord_span_mm=sum(c.span_mm for c in chord_scores) / n_chords,
        max_chord_span_mm=max((c.span_mm for c in chord_scores), default=0.0),
        mean_fingers=sum(c.num_fingers for c in chord_scores) / n_chords,
        barre_count=sum(c.barre for c in chord_scores),
        mean_chord_difficulty_score=sum(c.score for c in chord_scores) / n_chords,
        mean_transition_physical_mm=sum(t.total_mm for t in transitions) / n_trans,
        max_transition_physical_mm=max((t.total_mm for t in transitions), default=0.0),
        barre_changes=sum(t.barre_change for t in transitions),
        total_physical_distance_mm=sum(t.total_mm for t in transitions),
        mean_minimal_voice_leading=sum(harmonic) / n_trans,
        total_minimal_voice_leading=sum(harmonic),
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo():
    print(f"=== Vokabular: {len(CHORD_SHAPES)} manuell definierte Akkorde ===\n")

    print("Beispielgriffe (manuell definiert):")
    for label in ["C", "G", "F", "Am", "Dm", "Em", "D", "A", "Bdim", "F#dim"]:
        if label in CHORD_SHAPES:
            d = chord_difficulty(CHORD_SHAPES[label])
            print(f"  {label:>5}: {CHORD_SHAPES[label]}  "
                  f"(span={d.span_mm:5.1f}mm, fingers={d.num_fingers}, barre={d.barre})")
    print()

    print("=== Akkordfolgen: physisch vs. minimale Voice-Leading-Distanz ===\n")
    progressions = {
        "I-IV-V-I (C-Dur)": ["C", "F", "G", "C"],
        "I-vi-ii-V (C-Dur)": ["C", "Am", "Dm", "G"],
        "Em -> E -> Em -> E (harmonisch nah, physisch teuer)": ["Em", "E", "Em", "E"],
    }
    for label, prog in progressions.items():
        feats = progression_physical_features(prog)
        print(f"-- {label}: {prog}")
        print(f"   mean physische Uebergangsdistanz : {feats['mean_transition_physical_mm']:.1f} mm")
        print(f"   mean minimale Voice-Leading-Distanz: {feats['mean_minimal_voice_leading']:.1f}")
        print(f"   Barre-Wechsel unterwegs            : {feats['barre_changes']}\n")

    print("=== Korrelationstest ueber alle Akkordpaare mit gefundener Position ===\n")
    labels = list(CHORD_SHAPES.keys())
    phys, harm = [], []
    for a, b in itertools.combinations(labels, 2):
        t = chord_transition_distance(CHORD_SHAPES[a], CHORD_SHAPES[b])
        h = minimal_voice_leading_distance(CHORD_VOCAB[a]["pitch_classes"], CHORD_VOCAB[b]["pitch_classes"])
        phys.append(t.total_mm)
        harm.append(h)
    r = _pearson(phys, harm)
    print(f"Pearson r (physisch vs. harmonisch), n={len(phys)} Paare: {r:.3f}")

    print("=== Melodie-Beispiel (C-Dur-Tonleiter, 8 Toene) ===\n")
    c_major_scale_midi = [60, 62, 64, 65, 67, 69, 71, 72]
    mf = melody_physical_features(c_major_scale_midi)
    for k, v in mf.items():
        print(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}")


if __name__ == "__main__":
    _demo()