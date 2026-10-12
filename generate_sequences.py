"""
generate_sequences.py
=============================
Draws random chord progressions and melodies from the vocabularies.
Sequences are lists of variant IDs, e.g. ['C (Var. 1)', 'Am (Var. 2)', ...].
Labels are drawn first (with the musical rules), the variation per position
is then drawn uniformly among the variations of that label.
"""

import random
from typing import Dict, List, Optional
import config
from chord_vocab import CHORD_VARIANTS
from tone_vocab import TONE_VARIANTS, TONE_VOCAB


def _draw_unique(n: int, draw_one, space_hint: str) -> List[List[str]]:
    seen, out = set(), []
    attempts, max_attempts = 0, n * 100 + 1000
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        ids = tuple(draw_one())
        if ids in seen:
            continue
        seen.add(ids)
        out.append(list(ids))
    if len(out) < n:
        raise ValueError(f"Only {len(out)} unique sequences found for n={n} ({space_hint}). "
                         f"Lower n or enlarge the vocabulary / length.")
    return out


def generate_progressions(
    n: int,
    length: int = config.PROGRESSION_LENGTH,
    seed: Optional[int] = config.SEED,
    allow_repeat: bool = config.ALLOW_CHORD_REPEAT,
    variants: Dict[str, List[str]] = None,
) -> List[List[str]]:
    """n unique chord progressions of the given length (labels free, no key)."""
    variants = variants or CHORD_VARIANTS
    labels = list(variants)
    if length > 1 and not allow_repeat and len(labels) < 2:
        raise ValueError("Need at least 2 chord labels when repeats are not allowed.")
    rng = random.Random(seed)

    def draw_one():
        seq = [rng.choice(labels)]
        while len(seq) < length:
            cand = rng.choice(labels)
            if not allow_repeat and cand == seq[-1]:
                continue
            seq.append(cand)
        return [rng.choice(variants[l]) for l in seq]

    return _draw_unique(n, draw_one, f"{len(labels)} chords, length {length}")


def generate_melodies(
    n: int,
    length: int = config.MELODY_LENGTH,
    seed: Optional[int] = config.SEED,
    max_leap: int = config.MAX_MELODY_LEAP,
    allow_repeat: bool = config.ALLOW_TONE_REPEAT,
    variants: Dict[str, List[str]] = None,
    vocab: Dict[str, Dict] = None,
) -> List[List[str]]:
    """n unique melodies of the given length: all tones, any key,
    consecutive tones at most `max_leap` semitones apart."""
    variants = variants or TONE_VARIANTS
    vocab = vocab or TONE_VOCAB
    midi_of = {label: vocab[ids[0]]["midi"] for label, ids in variants.items()}
    labels = list(variants)
    rng = random.Random(seed)

    def draw_one():
        seq = [rng.choice(labels)]
        while len(seq) < length:
            prev = midi_of[seq[-1]]
            cands = [l for l in labels
                     if abs(midi_of[l] - prev) <= max_leap and (allow_repeat or l != seq[-1])]
            seq.append(rng.choice(cands))
        return [rng.choice(variants[l]) for l in seq]

    return _draw_unique(n, draw_one, f"{len(labels)} tones, length {length}, max leap {max_leap}")