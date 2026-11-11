"""
music_theory.py
=============================
Small music-theory helpers shared by the melody strand and the (later) chord strand.

Conventions used everywhere in the pipeline:
- Pitches are MIDI note numbers (60 = C4, middle C; 72 = C5).
- A pitch class (pc) is pitch % 12 (0 = C, 1 = C#, ... 11 = B).
- Note names use sharps only (no flats), so a mode-swap probe that lowers E prints 'D#', not 'Eb'.
"""

from typing import Dict, Iterable, Set, Tuple

# Pitch-class names, index = pitch class. Sharps only, no flats.
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Semitones above the tonic of the seven degrees of a major scale (1 2 3 4 5 6 7).
MAJOR_SCALE_STEPS = [0, 2, 4, 5, 7, 9, 11]

# Key name -> pitch class of its tonic, for all 12 major keys ('C' -> 0, 'G' -> 7, ...).
# Used for the key of a set (config.KEY), for played transpositions (config.TRANSPOSITION_KEY) and for scale degrees.
ALL_KEY_ROOTS: Dict[str, int] = {name: pc for pc, name in enumerate(NOTE_NAMES)}


def variant_id(label: str, variant: int) -> str:
    """ID of one way to play a chord/tone, e.g. 'Am (Var. 2)'. Kept for the chord strand (legacy naming)."""
    return f"{label} (Var. {variant})"


def midi_to_tone_name(midi: int) -> str:
    """Scientific pitch name: 60 -> 'C4', 72 -> 'C5'. (MIDI octave numbering: octave = midi // 12 - 1.)"""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def major_scale_pcs(key_name: str, key_roots: Dict[str, int] = ALL_KEY_ROOTS) -> Set[int]:
    """Pitch classes of a major key, e.g. 'C' -> {0, 2, 4, 5, 7, 9, 11}, 'G' -> {7, 9, 11, 0, 2, 4, 6}."""
    root = key_roots[key_name]
    return {(root + step) % 12 for step in MAJOR_SCALE_STEPS}


def best_key_fit(
    pc_sets: Iterable[Iterable[int]],
    key_roots: Dict[str, int] = ALL_KEY_ROOTS,
) -> Tuple[str, float]:
    """Major key with the smallest share of 'out of key' elements.

    pc_sets: one pitch class set per element (per chord, or {pc} per tone).
    An element is out of key if at least one of its pitch classes is not in the scale.
    Returns (key name, out_of_key_ratio). Ties go to the first key in NOTE_NAMES order.
    Not used by the melody pipeline (it fixes the key in config); kept for the chord strand."""
    pc_sets = [set(s) for s in pc_sets]
    best_name, best_ratio = None, None
    for name in key_roots:
        scale = major_scale_pcs(name, key_roots)
        # share of elements with at least one pitch class outside this key
        ratio = sum(1 for s in pc_sets if not s <= scale) / len(pc_sets)
        if best_ratio is None or ratio < best_ratio:
            best_name, best_ratio = name, ratio
    return best_name, best_ratio
