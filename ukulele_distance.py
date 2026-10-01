"""
ukulele_physical_distance.py
=============================

"""

from __future__ import annotations
import itertools
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1. Ukulele-Geometrie 
# ---------------------------------------------------------------------------

STRING_ORDER: Tuple[str, str, str, str] = ("G", "C", "E", "A")
OPEN_STRING_MIDI: Dict[str, int] = {"G": 67, "C": 60, "E": 64, "A": 69}
STRING_SPACING_MM: float = 11.0

SCALE_LENGTHS_MM = {"soprano": 340.0, "concert": 380.0, "tenor": 430.0}
DEFAULT_SCALE_LENGTH_MM = SCALE_LENGTHS_MM["soprano"]


def fret_position_mm(fret: int, scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physische Distanz eines Bundes vom Sattel (nut), nach der
    "Rule of 18": D(n) = scale_length * (1 - 2^(-n/12)). fret=0 -> 0.0."""
    if fret <= 0:
        return 0.0
    return scale_length_mm * (1 - 2 ** (-fret / 12))


def fretboard_euclidean_mm(
    pos_a: Tuple[str, int],
    pos_b: Tuple[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
) -> float:
    """Euklidische physische Distanz zwischen zwei Griffbrett-Positionen
    (Saite, Bund): "along" (nichtlinearer Bundabstand) + "across"
    (linearer Saitenabstand)."""
    str_a, fret_a = pos_a
    str_b, fret_b = pos_b
    dx = fret_position_mm(fret_b, scale_length_mm) - fret_position_mm(fret_a, scale_length_mm)
    dy = (STRING_ORDER.index(str_b) - STRING_ORDER.index(str_a)) * STRING_SPACING_MM
    return math.hypot(dx, dy)


def midi_from_object(obj) -> int:
    """Duck-Typing-Adapter fuer rohe int MIDI-Nummern oder music21-Objekte."""
    if isinstance(obj, int):
        return obj
    if hasattr(obj, "pitch") and hasattr(obj.pitch, "midi"):
        return int(obj.pitch.midi)
    if hasattr(obj, "midi"):
        return int(obj.midi)
    return int(obj)


# ---------------------------------------------------------------------------
# 2. Griff-Geometrie 
# ---------------------------------------------------------------------------

def is_barre(chord_shape: Dict[str, int]) -> bool:
    """Heuristik: 3+ Saiten am selben nicht-leeren Bund -> Barre.
    Caveat: markiert z.B. auch D (2-2-2-0) als Barre, obwohl das ueblicher-
    weise mit 3 Einzelfingern gegriffen wird - vor produktivem Einsatz ggf.
    verschaerfen (z.B. zusaetzlich Bund >= 3 verlangen)."""
    frets = [f for f in chord_shape.values() if f > 0]
    if not frets:
        return False
    most_common_count = max(frets.count(f) for f in set(frets))
    return most_common_count >= 3


def chord_span_mm(chord_shape: Dict[str, int], scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> float:
    """Physische Spannweite der Greifhand (mm) zwischen niedrigstem und
    hoechstem gegriffenen (nicht-leeren) Bund."""
    fretted = [f for f in chord_shape.values() if f > 0]
    if not fretted:
        return 0.0
    positions = [fret_position_mm(f, scale_length_mm) for f in fretted]
    return max(positions) - min(positions)


def num_fingers_required(chord_shape: Dict[str, int]) -> int:
    """Grobe Schaetzung der benoetigten Finger (Barre zaehlt einmal)."""
    fretted = [f for f in chord_shape.values() if f > 0]
    if not fretted:
        return 0
    if is_barre(chord_shape):
        barre_fret = max(set(fretted), key=fretted.count)
        other_frets = {f for f in fretted if f != barre_fret}
        return 1 + len(other_frets)
    return len(set(fretted)) if len(set(fretted)) == len(fretted) else len(fretted)


@dataclass
class ChordDifficulty:
    span_mm: float
    num_fingers: int
    barre: bool
    score: float


DEFAULT_WEIGHTS = dict(span=1.0, fingers=3.0, barre=8.0)


def chord_difficulty(
    chord_shape: Dict[str, int],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    weights: Dict[str, float] = None,
) -> ChordDifficulty:
    """Einzelgriff-Schwierigkeit (unabhaengig von Uebergaengen), transparente
    Rohkomponenten statt Blackbox-Zahl - editierbar/validierbar gegen
    Pilotdaten."""
    weights = weights or DEFAULT_WEIGHTS
    span = chord_span_mm(chord_shape, scale_length_mm)
    fingers = num_fingers_required(chord_shape)
    barre = is_barre(chord_shape)
    score = weights["span"] * span + weights["fingers"] * fingers + weights["barre"] * barre
    return ChordDifficulty(span_mm=span, num_fingers=fingers, barre=barre, score=score)


@dataclass
class TransitionDistance:
    hand_shift_mm: float
    finger_movement_mm: float
    barre_change: bool
    total_mm: float


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


# ---------------------------------------------------------------------------
# 3. Akkordvokabular: algorithmisch gefundene Griffe statt abgetippter Tabelle
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

# Standard-Tonartenset fuers Stimulus-Design (erweiterbar). Tonart -> Grundton-
# Tonklasse (C=0, C#=1, ..., B=11).
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
    """Stufe -> Akkordlabel fuer eine Tonart, z.B. {'I': 'C', 'ii': 'Dm', ...,
    'vii°': 'Bdim'}. Praktisch, um Roman-Numeral-Progressionen (wie in der
    Original-Pipeline verwendet) in konkrete Akkordlabels zu uebersetzen."""
    root = key_roots[key_name]
    out = {}
    for step, quality, degree_label in zip(MAJOR_SCALE_STEPS, DEGREE_QUALITIES, DEGREE_LABELS):
        chord_root = (root + step) % 12
        out[degree_label] = chord_label(chord_root, quality)
    return out


# Definierte Griffe
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
# 4. Harmonische Distanz: echte minimale Voice-Leading-Distanz
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 5. Aggregierte Features fuer eine Akkordfolge (Stimulus-Matching)
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
# 6. Analoges Distanzmass fuer Melodien 
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 7. Hilfsfunktion + Demo
# ---------------------------------------------------------------------------

def _pearson(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = (sum((x - mx) ** 2 for x in xs) / n) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys) / n) ** 0.5
    return cov / (sx * sy)


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