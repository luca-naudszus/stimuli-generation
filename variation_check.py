"""
variation_check.py
=============================
Tests whether the chosen variations are 'unnecessary': would another variation
of the same chord/tone at that position be easier? Variations only change the
physical side (same pitch classes / same pitch), so only physical costs count.

Two cost types are evaluated separately:
  - transition: physical distance in mm between consecutive elements
  - fingers:    number of fingers needed per element

Per type:
  local check   position i is 'unnecessary' if swapping ONLY that position
                (all others fixed) lowers the cost by more than the tolerance.
  global check  optimal choice of all variations (labels fixed, Viterbi) vs.
                the chosen one -> optimality gap.
"""

from functools import lru_cache
from typing import Callable, Dict, List, Sequence

import config
from ukulele_geometry import DEFAULT_SCALE_LENGTH_MM, fretboard_euclidean_mm
from chord_vocab import CHORD_VOCAB, CHORD_VARIANTS
from chord_difficulty import chord_transition_distance, num_fingers_required
from tone_vocab import TONE_VOCAB, TONE_VARIANTS


@lru_cache(maxsize=None)
def _chord_trans(a: str, b: str, scale_length_mm: float) -> float:
    return chord_transition_distance(CHORD_VOCAB[a]["shape"], CHORD_VOCAB[b]["shape"], scale_length_mm).total_mm


@lru_cache(maxsize=None)
def _chord_fingers(a: str) -> float:
    return float(num_fingers_required(CHORD_VOCAB[a]["shape"]))


@lru_cache(maxsize=None)
def _tone_trans(a: str, b: str, scale_length_mm: float) -> float:
    return fretboard_euclidean_mm(TONE_VOCAB[a]["position"], TONE_VOCAB[b]["position"], scale_length_mm)


@lru_cache(maxsize=None)
def _tone_fingers(a: str) -> float:
    return 1.0 if TONE_VOCAB[a]["position"][1] > 0 else 0.0


def _viterbi_path(alts: List[List[str]], trans: Callable[[str, str], float],
                  fingers: Callable[[str], float]) -> List[str]:
    """Variant path with minimal total transition cost (mm). Ties (within 1e-6 mm)
    are broken by the smaller total number of fingers, then by vocabulary order."""
    layers = [{a: ((0.0, fingers(a)), None) for a in alts[0]}]
    for i in range(1, len(alts)):
        prev = layers[-1]
        layer = {}
        for b in alts[i]:
            best_cost, best_a = None, None
            for a in prev:
                cost = (round(prev[a][0][0] + trans(a, b), 6), prev[a][0][1] + fingers(b))
                if best_cost is None or cost < best_cost:
                    best_cost, best_a = cost, a
            layer[b] = (best_cost, best_a)
        layers.append(layer)
    last = min(layers[-1], key=lambda b: layers[-1][b][0])
    path = [last]
    for i in range(len(layers) - 1, 0, -1):
        path.append(layers[i][path[-1]][1])
    return path[::-1]


def optimal_progression_ids(labels: Sequence[str],
                            scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> List[str]:
    """Best variant ID for every chord label of a progression."""
    alts = [CHORD_VARIANTS[l] for l in labels]
    return _viterbi_path(alts, lambda a, b: _chord_trans(a, b, scale_length_mm), _chord_fingers)


def optimal_melody_ids(labels: Sequence[str],
                       scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM) -> List[str]:
    """Best variant ID (string/fret position) for every tone label of a melody."""
    alts = [TONE_VARIANTS[l] for l in labels]
    return _viterbi_path(alts, lambda a, b: _tone_trans(a, b, scale_length_mm), _tone_fingers)


def _viterbi_min_cost(alts: List[List[str]], trans: Callable[[str, str], float]) -> float:
    """Minimal total transition cost when every position may use any of its alternatives."""
    best = {a: 0.0 for a in alts[0]}
    for i in range(1, len(alts)):
        best = {b: min(best[a] + trans(a, b) for a in best) for b in alts[i]}
    return min(best.values())


def _variation_features(
    chosen: Sequence[str],
    alts: List[List[str]],
    trans: Callable[[str, str], float],
    fingers: Callable[[str], float],
    tol_trans: float,
    tol_fingers: float,
) -> Dict[str, float]:
    n = len(chosen)

    def local_trans(i: int, v: str) -> float:
        c = 0.0
        if i > 0:
            c += trans(chosen[i - 1], v)
        if i < n - 1:
            c += trans(v, chosen[i + 1])
        return c

    saving_t, saving_f = [], []
    for i in range(n):
        saving_t.append(max(0.0, local_trans(i, chosen[i]) - min(local_trans(i, v) for v in alts[i])))
        saving_f.append(max(0.0, fingers(chosen[i]) - min(fingers(v) for v in alts[i])))

    chosen_total_t = sum(trans(chosen[i], chosen[i + 1]) for i in range(n - 1))
    opt_total_t = _viterbi_min_cost(alts, trans)
    gap_t = max(0.0, chosen_total_t - opt_total_t)

    chosen_total_f = sum(fingers(c) for c in chosen)
    opt_total_f = sum(min(fingers(v) for v in a) for a in alts)
    gap_f = max(0.0, chosen_total_f - opt_total_f)

    return dict(
        var_n_positions_with_alternatives=float(sum(1 for a in alts if len(a) > 1)),
        var_unnecessary_ratio_transition=sum(1 for s in saving_t if s > tol_trans) / n,
        var_mean_avoidable_transition_mm=sum(saving_t) / n,
        var_max_avoidable_transition_mm=max(saving_t),
        var_optimality_gap_transition_mm=gap_t,
        var_optimality_gap_transition_rel=gap_t / chosen_total_t if chosen_total_t > 0 else 0.0,
        var_unnecessary_ratio_fingers=sum(1 for s in saving_f if s > tol_fingers) / n,
        var_mean_avoidable_fingers=sum(saving_f) / n,
        var_optimality_gap_fingers=gap_f,
        var_optimality_gap_fingers_rel=gap_f / chosen_total_f if chosen_total_f > 0 else 0.0,
    )


def variation_features_progression(
    chord_ids: Sequence[str],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    tol_trans: float = config.VARIATION_TOLERANCE_TRANSITION_MM,
    tol_fingers: float = config.VARIATION_TOLERANCE_FINGERS,
) -> Dict[str, float]:
    @lru_cache(maxsize=None)
    def trans(a: str, b: str) -> float:
        return chord_transition_distance(CHORD_VOCAB[a]["shape"], CHORD_VOCAB[b]["shape"],
                                         scale_length_mm).total_mm

    @lru_cache(maxsize=None)
    def fingers(a: str) -> float:
        return float(num_fingers_required(CHORD_VOCAB[a]["shape"]))

    alts = [CHORD_VARIANTS[CHORD_VOCAB[c]["label"]] for c in chord_ids]
    return _variation_features(chord_ids, alts, trans, fingers, tol_trans, tol_fingers)


def variation_features_melody(
    tone_ids: Sequence[str],
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    tol_trans: float = config.VARIATION_TOLERANCE_TRANSITION_MM,
    tol_fingers: float = config.VARIATION_TOLERANCE_FINGERS,
) -> Dict[str, float]:
    """Fingers for a tone: 1 if fretted, 0 if open string."""
    @lru_cache(maxsize=None)
    def trans(a: str, b: str) -> float:
        return fretboard_euclidean_mm(TONE_VOCAB[a]["position"], TONE_VOCAB[b]["position"], scale_length_mm)

    @lru_cache(maxsize=None)
    def fingers(a: str) -> float:
        return 1.0 if TONE_VOCAB[a]["position"][1] > 0 else 0.0

    alts = [TONE_VARIANTS[TONE_VOCAB[t]["label"]] for t in tone_ids]
    return _variation_features(tone_ids, alts, trans, fingers, tol_trans, tol_fingers)