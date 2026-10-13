"""
generate_sequences.py
=============================
Draws random chord progressions and melodies from the vocabularies.
Labels are drawn first (with the musical rules), variants are assigned afterwards:
'optimal' (default, Viterbi: minimal transition mm) or 'random'.
Uniqueness is checked on label level, so the same label sequence never appears twice.
Sequences are returned as lists of variant IDs, e.g. ['C (Var. 1)', 'Am (Var. 2)', ...].
"""

import itertools
import random
from typing import Dict, List, Optional, Sequence, Tuple

import config
from chord_vocab import CHORD_VARIANTS
from tone_vocab import TONE_VARIANTS, TONE_VOCAB
from variation_check import optimal_progression_ids, optimal_melody_ids


def _space_size(k: int, length: int, allow_repeat: bool) -> int:
    if length <= 0:
        return 0
    return k ** length if allow_repeat else k * (k - 1) ** (length - 1)


def _draw_unique_labels(n: int, draw_one, hint: str) -> List[Tuple[str, ...]]:
    seen, out = set(), []
    attempts, max_attempts = 0, n * 100 + 1000
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        seq = tuple(draw_one())
        if seq in seen:
            continue
        seen.add(seq)
        out.append(seq)
    if len(out) < n:
        raise ValueError(f"Only {len(out)} unique sequences found for n={n} ({hint}). "
                         f"Lower n or enlarge the vocabulary / length.")
    return out


def _assign_variants(label_seqs, mode: str, rng: random.Random, variants, optimal_fn) -> List[List[str]]:
    if mode == "optimal":
        return [optimal_fn(list(s)) for s in label_seqs]
    if mode == "random":
        return [[rng.choice(variants[l]) for l in s] for s in label_seqs]
    raise ValueError(f"Unknown variant_mode: {mode!r} (use 'optimal' or 'random')")


def generate_progressions(
    n: int,
    length: int = config.PROGRESSION_LENGTH,
    seed: Optional[int] = config.SEED,
    allow_repeat: bool = config.ALLOW_CHORD_REPEAT,
    variants: Dict[str, List[str]] = None,
    variant_mode: str = config.VARIANT_MODE,
    allow_fewer: bool = False,
) -> List[List[str]]:
    """n chord progressions with unique label sequences (labels free, no key).
    If n exceeds the number of possible label sequences: error, or all of them with allow_fewer=True.
    Note: 'optimal' variants always refer to the global CHORD_VARIANTS."""
    variants = variants or CHORD_VARIANTS
    labels = list(variants)
    rng = random.Random(seed)
    space = _space_size(len(labels), length, allow_repeat)
    if n > space:
        if not allow_fewer:
            raise ValueError(f"Only {space} label sequences possible, n={n} requested.")
        n = space

    if n >= 0.3 * space:   # (nearly) exhaustive: enumerate instead of rejection sampling
        everything = [s for s in itertools.product(labels, repeat=length)
                      if allow_repeat or all(a != b for a, b in zip(s, s[1:]))]
        label_seqs = rng.sample(everything, n)
    else:
        def draw_one():
            seq = [rng.choice(labels)]
            while len(seq) < length:
                cand = rng.choice(labels)
                if not allow_repeat and cand == seq[-1]:
                    continue
                seq.append(cand)
            return seq
        label_seqs = _draw_unique_labels(n, draw_one, f"{len(labels)} chords, length {length}")
    return _assign_variants(label_seqs, variant_mode, rng, variants, optimal_progression_ids)


def generate_melodies(
    n: int,
    length: int = config.MELODY_LENGTH,
    seed: Optional[int] = config.SEED,
    max_leap: int = config.MAX_MELODY_LEAP,
    allow_repeat: bool = config.ALLOW_TONE_REPEAT,
    variants: Dict[str, List[str]] = None,
    vocab: Dict[str, Dict] = None,
    variant_mode: str = config.VARIANT_MODE,
) -> List[List[str]]:
    """n melodies with unique label sequences: all tones, any key,
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
        return seq

    label_seqs = _draw_unique_labels(n, draw_one,
                                     f"{len(labels)} tones, length {length}, max leap {max_leap}")
    return _assign_variants(label_seqs, variant_mode, rng, variants, optimal_melody_ids)