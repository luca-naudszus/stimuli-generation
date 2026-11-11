"""
models.py
=============================
Model representational dissimilarity matrices (RDMs) over played items (build spec section 8).

An RDM is an items x items matrix of predicted dissimilarities: entry (i, j) says how different a model expects
items i and j to be (0 = identical). Each model is a hypothesis about what a brain region codes. The separability
analysis (separability.py) then asks whether two models make different predictions over the item set. Three kinds:
  - count models: each item becomes a bag of units (e.g. its 4 musical chunk IDs); the bag becomes a count vector,
    normalised to length 1, and distance = 1 - cosine similarity. Order inside the item does not matter.
  - identity models: 0 if two items have exactly the same key (e.g. the same pitch sequence), else 1.
  - graded models: 1 - share of positions (note by note) that match on some feature.

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
Single motor features (M-IV collinearity reports, build spec section 8):
  finger, fret, string       per-note left-hand finger / fret / string (count models)
Auditory features (A-IV, split into concrete / relational / tonal; build spec section 8):
  interval_size              per-transition |interval| (count model)
  musical_boundary           (boundary 1-3, |boundary interval|): the boundary-cue profile (count model)
Combination components (C-VIII), from graded similarities between items i and j:
  s_sound  = share of the 12 positions with the same absolute pitch
  s_move   = share of positions with the same (fret, finger, relative string step)
  s_struct = share of the 11 intervals that match
  comb_sound = 1 - s_sound, comb_movement = 1 - s_move, comb_structure = 1 - s_struct,
  comb_interaction = 1 - share of positions where pitch AND movement match (multiplicative model),
  comb_interaction_product = 1 - s_sound * s_move (alternative form, exported for comparison)
Auditory models (AUDITORY_MODELS) need no fingering, so they can also be computed over listen-only items.
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
                "abs_pitch", "intervals", "contour", "scale_degree", "nuis_phrase_position", "nuis_beat_degree",
                "finger", "fret", "string", "interval_size", "musical_boundary"]
IDENTITY_MODELS = ["concrete_sound", "abstract_structure", "movement_identity"]
COMBINATION_MODELS = ["comb_sound", "comb_movement", "comb_interaction", "comb_interaction_product", "comb_structure"]
GRADED_MODELS = ["movement_graded"] + COMBINATION_MODELS
MODELS = COUNT_MODELS + IDENTITY_MODELS + GRADED_MODELS

NUISANCE_MODELS = ["scale_degree", "nuis_phrase_position", "nuis_beat_degree"]
# C-VIII components whose collinearity is reported (build spec section 8); the product form is the alternative
C8_COMPONENTS = ["comb_sound", "comb_movement", "comb_interaction", "comb_structure"]
C8_COMPONENTS_PRODUCT = ["comb_sound", "comb_movement", "comb_interaction_product", "comb_structure"]
# A-IV split of the auditory feature models
AUDITORY_GROUPS = {"concrete": ["abs_pitch", "concrete_sound"],
                   "relational": ["intervals", "contour", "interval_size", "abstract_structure", "abstract_chunk"],
                   "tonal": ["scale_degree"]}
AUDITORY_MODELS = {"musical_chunk", "abstract_chunk", "abs_pitch", "intervals", "contour", "scale_degree",
                   "nuis_phrase_position", "nuis_beat_degree", "interval_size", "musical_boundary",
                   "concrete_sound", "abstract_structure", "comb_sound", "comb_structure"}

# Build spec section 8a: which research questions a model serves and what it must separate from
MODEL_SERVES = [
    ("motor_elements, finger, fret, string", "M-II, M-IV", "concrete sound (as far as first position allows; report)"),
    ("movement_identity, movement_graded", "M-IV, C-IV, C-VII", "concrete sound, abstract structure"),
    ("concrete_sound, abs_pitch", "A-IV, C-IV, C-VII", "movement, abstract structure"),
    ("intervals, contour, interval_size (relational); scale_degree (tonal)", "A-IV", "concrete sound (via transposed items; report)"),
    ("abstract_structure, abstract_chunk", "C-IV, C-VIII", "concrete sound, movement"),
    ("comb_sound, comb_movement, comb_interaction, comb_structure", "C-VIII", "each other (variance inflation)"),
    ("musical_chunk", "A-III, C-III, C-VIII", "motor chunks (misaligned), sequence, nuisance"),
    ("motor_chunk_{aligned,misal}_{full,lh}", "M-III, C-III, C-VIII", "musical chunks, sequence, nuisance"),
    ("concrete_sound / movement_identity as sequence identity", "III (all domains)", "chunk models"),
    ("prop_trained_* (item table)", "III (all domains), C-IX", "-"),
    ("scale_degree, nuis_phrase_position, nuis_beat_degree", "all levels", "- (chunk models must not be explained by them)"),
]


def _comp(item: Item):
    """The item's misaligned composition (aligned 3-3-3-3 for items without one)."""
    return item.composition or vs.aligned_composition()


def _move_tokens(item: Item):
    """Per note: (fret, finger, string step from the previous note; 0 for the first note)."""
    steps = (0,) + fb.relative_string_pattern(item.positions)
    return tuple((p.fret, p.finger, s) for p, s in zip(item.positions, steps))


def count_units(item: Item, model: str) -> Counter:
    """The bag of units an item contributes to a count model (see the module docstring for each model).
    Example for B1 and 'musical_chunk': Counter({'C4-D4-E4': 1, 'D4-E4-F4': 1, 'E4-F4-G4': 1, 'F4-G4-A4': 1}).
    Motor models need positions; auditory models use only pitches, chunk IDs and the key."""
    pos, comp, n = item.positions, _comp(item), config.CHUNK_LEN
    iv = [b - a for a, b in zip(item.pitches, item.pitches[1:])]
    degrees = [keys.scale_degree(p, item.key) for p in item.pitches]
    if model == "motor_elements":
        return Counter((p.string, p.fret, p.finger) for p in pos)
    # motor chunk models: the suffix after the last '_' is the identity mode ('full' or 'lh')
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
    # nuisance: which chunk sits at which position (1-4); recombination moves chunks to other positions
    if model == "nuis_phrase_position":
        return Counter((i // n, item.chunk_ids[i // n]) for i in range(config.N_NOTES))
    # nuisance: which scale degree falls on which beat of the bar
    if model == "nuis_beat_degree":
        return Counter((i % config.BEATS_PER_BAR, d) for i, d in enumerate(degrees))
    if model == "finger":
        return Counter(p.finger for p in pos)
    if model == "fret":
        return Counter(p.fret for p in pos)
    if model == "string":
        return Counter(p.string for p in pos)
    if model == "interval_size":
        return Counter(abs(x) for x in iv)
    # boundary-cue profile: interval size at boundary 1, 2, 3 (transitions 3, 6, 9; iv is 0-based, so iv[t - 1]) (Q17)
    if model == "musical_boundary":
        return Counter((k, abs(iv[t - 1])) for k, t in enumerate(sorted(vs.musical_boundaries())))
    raise KeyError(model)


def identity_key(item: Item, model: str):
    """What two items must share to count as identical under an identity model."""
    if model == "concrete_sound":
        return item.pitches
    if model == "abstract_structure":
        return keys.interval_pattern(item.pitches)
    if model == "movement_identity":
        return tuple((p.fret, p.finger) for p in item.positions) + fb.relative_string_pattern(item.positions)
    raise KeyError(model)


def _cosine_rdm(counters: Sequence[Counter]) -> np.ndarray:
    """1 - cosine similarity between count vectors. Columns = every unit seen in any item (sorted for stability).
    Clipped at 0 to remove tiny negative values from floating-point error."""
    ks = sorted({k for c in counters for k in c}, key=str)
    X = np.array([[c.get(k, 0) for k in ks] for c in counters], dtype=float)
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.where(norm == 0, 1, norm)          # unit length (an empty bag stays zero)
    return np.clip(1 - X @ X.T, 0, None)


def _identity_rdm(keys_: Sequence) -> np.ndarray:
    """0 where the keys are equal, 1 elsewhere."""
    n = len(keys_)
    return np.array([[0.0 if keys_[i] == keys_[j] else 1.0 for j in range(n)] for i in range(n)])


def _share(xs, ys) -> float:
    """Share of positions where two equally long sequences agree."""
    return sum(a == b for a, b in zip(xs, ys)) / len(xs)


def _graded_rdm(items: Sequence[Item], model: str) -> np.ndarray:
    """Position-by-position models: movement_graded and the C-VIII combination components.
    Movement tokens per note = (fret, finger, string step); pitch per note; interval per transition."""
    n = len(items)
    pit = [i.pitches for i in items]
    ivs = [tuple(b - a for a, b in zip(p, p[1:])) for p in pit]
    mov = [_move_tokens(i) if i.played else None for i in items]
    M = np.zeros((n, n))
    for a in range(n):
        for b in range(a + 1, n):
            if model in ("movement_graded", "comb_movement"):
                d = 1 - _share(mov[a], mov[b])
            elif model == "comb_sound":
                d = 1 - _share(pit[a], pit[b])
            elif model == "comb_structure":
                d = 1 - _share(ivs[a], ivs[b])
            elif model == "comb_interaction":
                # joint match: a position counts only if pitch AND movement match there
                d = 1 - sum(pa == pb and ma == mb for pa, pb, ma, mb in zip(pit[a], pit[b], mov[a], mov[b])) / config.N_NOTES
            elif model == "comb_interaction_product":
                d = 1 - _share(pit[a], pit[b]) * _share(mov[a], mov[b])
            else:
                raise KeyError(model)
            M[a, b] = M[b, a] = d
    return M


def model_rdms(items: Sequence[Item], names: Optional[Sequence[str]] = None,
               include_listen_only: bool = False) -> Dict[str, np.ndarray]:
    """RDMs of the played items among `items` (listen-only items have no motor information and are skipped).
    include_listen_only=True keeps listen-only items too; then only AUDITORY_MODELS may be asked for."""
    use = list(items) if include_listen_only else [i for i in items if i.played]
    names = list(names or MODELS)
    if include_listen_only:
        bad = [m for m in names if m not in AUDITORY_MODELS]
        if bad:
            raise ValueError(f"models {bad} need a fingering; listen-only items cannot be included")
    out = {}
    for m in names:
        if m in COUNT_MODELS:
            out[m] = _cosine_rdm([count_units(i, m) for i in use])
        elif m in IDENTITY_MODELS:
            out[m] = _identity_rdm([identity_key(i, m) for i in use])
        else:
            out[m] = _graded_rdm(use, m)
    return out
