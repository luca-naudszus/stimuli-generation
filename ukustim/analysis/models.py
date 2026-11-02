"""
models.py
=============================
Model representational dissimilarity matrices (RDMs) over played items (build spec section 8).

Count-vector models (cosine distance on unit counts):
  motor_elements             (string, fret, finger) of each note
  motor_chunk_{aligned,misal}_{full,lh}
                             motor chunks under the aligned / the item's misaligned segmentation; 'full' identity =
                             string, fret, finger; 'lh' (left hand) = fret, finger, relative string pattern
  motor_chunk_crossing_lh    optional analysis contrast: only the misaligned motor chunks that cross a musical boundary
  musical_chunk              musical chunk IDs
  abstract_chunk             interval pattern of each musical chunk (a transposed chunk keeps it)
  abs_pitch, intervals, contour, scale_degree
  nuis_phrase_position       (position 1-4, musical chunk ID): nuisance
  nuis_beat_degree           (beat in bar, scale degree): tonal-metrical nuisance
Identity models (0 = same, 1 = different):
  concrete_sound             same absolute pitch sequence
  abstract_structure         same interval sequence (a transposition shares it)
  movement_identity          same fret, finger and relative string pattern (Q8); a string-pair shift shares it
Graded:
  movement_graded            1 - share of positions with the same (fret, finger, string step)
"""

from collections import Counter
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import keys
from ukustim.core import versions as vs
from ukustim.core.items import Item

COUNT_MODELS = ["motor_elements", "motor_chunk_aligned_full", "motor_chunk_misal_full", "motor_chunk_aligned_lh",
                "motor_chunk_misal_lh", "motor_chunk_crossing_lh", "musical_chunk", "abstract_chunk",
                "abs_pitch", "intervals", "contour", "scale_degree", "nuis_phrase_position", "nuis_beat_degree"]
IDENTITY_MODELS = ["concrete_sound", "abstract_structure", "movement_identity"]
GRADED_MODELS = ["movement_graded"]
MODELS = COUNT_MODELS + IDENTITY_MODELS + GRADED_MODELS

NUISANCE_MODELS = ["scale_degree", "nuis_phrase_position", "nuis_beat_degree"]


def _comp(item: Item):
    return item.composition or vs.aligned_composition()


def _move_tokens(item: Item):
    """Per note: (fret, finger, string step from the previous note; 0 for the first note)."""
    steps = (0,) + fb.relative_string_pattern(item.positions)
    return tuple((p.fret, p.finger, s) for p, s in zip(item.positions, steps))


def count_units(item: Item, model: str) -> Counter:
    pos, comp, n = item.positions, _comp(item), config.CHUNK_LEN
    iv = [b - a for a, b in zip(item.pitches, item.pitches[1:])]
    degrees = [keys.scale_degree(p, item.key) for p in item.pitches]
    if model == "motor_elements":
        return Counter((p.string, p.fret, p.finger) for p in pos)
    if model.startswith("motor_chunk_aligned"):
        return Counter(m for _, _, m in vs.motor_chunks(pos, vs.aligned_composition(), model.rsplit("_", 1)[1]))
    if model in ("motor_chunk_misal_full", "motor_chunk_misal_lh"):
        return Counter(m for _, _, m in vs.motor_chunks(pos, comp, model.rsplit("_", 1)[1]))
    if model == "motor_chunk_crossing_lh":
        return Counter(m for a, b, m in vs.motor_chunks(pos, comp, "lh") if vs.is_crossing(a, b))
    if model == "musical_chunk":
        return Counter(item.chunk_ids)
    if model == "abstract_chunk":
        return Counter(keys.interval_pattern(item.pitches[i * n:(i + 1) * n]) for i in range(config.N_CHUNKS))
    if model == "abs_pitch":
        return Counter(item.pitches)
    if model == "intervals":
        return Counter(iv)
    if model == "contour":
        return Counter((x > 0) - (x < 0) for x in iv)
    if model == "scale_degree":
        return Counter(degrees)
    if model == "nuis_phrase_position":
        return Counter((i // n, item.chunk_ids[i // n]) for i in range(config.N_NOTES))
    if model == "nuis_beat_degree":
        return Counter((i % config.BEATS_PER_BAR, d) for i, d in enumerate(degrees))
    raise KeyError(model)


def identity_key(item: Item, model: str):
    if model == "concrete_sound":
        return item.pitches
    if model == "abstract_structure":
        return keys.interval_pattern(item.pitches)
    if model == "movement_identity":
        return tuple((p.fret, p.finger) for p in item.positions) + fb.relative_string_pattern(item.positions)
    raise KeyError(model)


def _cosine_rdm(counters: Sequence[Counter]) -> np.ndarray:
    ks = sorted({k for c in counters for k in c}, key=str)
    X = np.array([[c.get(k, 0) for k in ks] for c in counters], dtype=float)
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.where(norm == 0, 1, norm)
    return np.clip(1 - X @ X.T, 0, None)


def _identity_rdm(keys_: Sequence) -> np.ndarray:
    n = len(keys_)
    return np.array([[0.0 if keys_[i] == keys_[j] else 1.0 for j in range(n)] for i in range(n)])


def model_rdms(items: Sequence[Item], names: Optional[Sequence[str]] = None) -> Dict[str, np.ndarray]:
    """RDMs of the played items among `items` (listen-only items have no motor information and are skipped)."""
    played = [i for i in items if i.played]
    out = {}
    for m in (names or MODELS):
        if m in COUNT_MODELS:
            out[m] = _cosine_rdm([count_units(i, m) for i in played])
        elif m in IDENTITY_MODELS:
            out[m] = _identity_rdm([identity_key(i, m) for i in played])
        else:
            toks = [_move_tokens(i) for i in played]
            n = len(played)
            out[m] = np.array([[1 - sum(a == b for a, b in zip(toks[i], toks[j])) / config.N_NOTES
                                for j in range(n)] for i in range(n)])
    return out
