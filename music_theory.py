"""
music_theory.py
=============================
Small shared helpers used by both the chord and the melody strand.
"""

from typing import Dict, Iterable, Set, Tuple

# contains only #, no b
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MAJOR_SCALE_STEPS = [0, 2, 4, 5, 7, 9, 11]

# All 12 major keys (used for the automatic key fit)
ALL_KEY_ROOTS: Dict[str, int] = {name: pc for pc, name in enumerate(NOTE_NAMES)}


def variant_id(label: str, variant: int) -> str:
    """ID of one way to play a chord/tone, e.g. 'Am (Var. 2)'."""
    return f"{label} (Var. {variant})"


def midi_to_tone_name(midi: int) -> str:
    """Scientific pitch name: 60 -> 'C4', 72 -> 'C5'."""
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def major_scale_pcs(key_name: str, key_roots: Dict[str, int] = ALL_KEY_ROOTS) -> Set[int]:
    """Pitch classes of a major key, e.g. 'C' -> {0, 2, 4, 5, 7, 9, 11}."""
    root = key_roots[key_name]
    return {(root + step) % 12 for step in MAJOR_SCALE_STEPS}


def best_key_fit(
    pc_sets: Iterable[Iterable[int]],
    key_roots: Dict[str, int] = ALL_KEY_ROOTS,
) -> Tuple[str, float]:
    """Major key with the smallest share of 'out of key' elements.

    pc_sets: one pitch class set per element (per chord, or {pc} per tone).
    An element is out of key if at least one of its pitch classes is not in the scale.
    Returns (key name, out_of_key_ratio). Ties go to the first key in NOTE_NAMES order."""
    pc_sets = [set(s) for s in pc_sets]
    best_name, best_ratio = None, None
    for name in key_roots:
        scale = major_scale_pcs(name, key_roots)
        ratio = sum(1 for s in pc_sets if not s <= scale) / len(pc_sets)
        if best_ratio is None or ratio < best_ratio:
            best_name, best_ratio = name, ratio
    return best_name, best_ratio