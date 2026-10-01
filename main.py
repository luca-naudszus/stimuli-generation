"""
main.py
=============================

"""

from __future__ import annotations
import itertools
from typing import List

from chord_difficulty import chord_difficulty, chord_transition_distance
from harmonic_distance import minimal_voice_leading_distance
from melody_distance import melody_physical_features
from chord_vocab import CHORD_VOCAB, CHORD_SHAPES
from progression_features import progression_features

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

### Currently not in use
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
# Demo
# ---------------------------------------------------------------------------

def _demo():
    print(f"=== Vokabular: {len(CHORD_SHAPES)} manuell definierte Akkorde ===\n")

    print("Example chords:")
    # TODO: Define D, A, Bdim, F#dim
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
        feats = progression_features(prog)
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