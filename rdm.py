"""
rdm.py
=============================
Separability check of a finished set (build spec section 8): model RDMs over the played items and their
pairwise correlations. Models are defined by the unit IDs an item is built from:

  motor_elements       (string, fret, finger) of each note
  motor_chunk_aligned  motor chunks under the aligned segmentation (3+3+3+3)
  motor_chunk_misal    motor chunks under the item's misaligned composition
  musical_chunk        musical chunk IDs
  sequence_sound       identical pitch sequence = similar
  sequence_movement    identical (string, fret) sequence = similar
  sequence_fret_pattern identical (fret, finger) sequence = similar, whatever the string (a string-pair shift
                       keeps it; without it the movement-identity model is constant in first position)
  abs_pitch            pitches
  intervals            signed intervals
  contour              up / same / down

Dissimilarity: cosine distance on unit-count vectors (identity models: 0 / 1). Correlation: Spearman over
the upper triangle. With n conditions there are n(n-1)/2 pairs; both numbers are printed.
"""

import itertools
import math
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import spearmanr

import config
import versions as vs
from items import Item

MODELS = ["motor_elements", "motor_chunk_aligned", "motor_chunk_misal", "musical_chunk",
          "sequence_sound", "sequence_movement", "sequence_fret_pattern", "abs_pitch", "intervals", "contour"]

# pairs the spec asks about
KEY_PAIRS = [("musical_chunk", "motor_chunk_misal"),
             ("motor_chunk_misal", "sequence_sound"),
             ("motor_chunk_misal", "sequence_movement"),
             ("motor_chunk_misal", "sequence_fret_pattern"),
             ("motor_chunk_misal", "motor_chunk_aligned"),
             ("musical_chunk", "motor_chunk_aligned")]


def _units(item: Item) -> Dict[str, Counter]:
    pos = item.positions
    comp = item.composition or vs.aligned_composition()
    iv = [b - a for a, b in zip(item.pitches, item.pitches[1:])]
    return {
        "motor_elements": Counter((p.string, p.fret, p.finger) for p in pos),
        "motor_chunk_aligned": Counter(m for _, _, m in vs.motor_chunks(pos, vs.aligned_composition())),
        "motor_chunk_misal": Counter(m for _, _, m in vs.motor_chunks(pos, comp)),
        "musical_chunk": Counter(item.chunk_ids),
        "abs_pitch": Counter(item.pitches),
        "intervals": Counter(iv),
        "contour": Counter((x > 0) - (x < 0) for x in iv),
    }


def _cosine_rdm(counters: Sequence[Counter]) -> np.ndarray:
    keys = sorted({k for c in counters for k in c}, key=str)
    X = np.array([[c.get(k, 0) for k in keys] for c in counters], dtype=float)
    norm = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.where(norm == 0, 1, norm)
    return np.clip(1 - X @ X.T, 0, None)


def _identity_rdm(keys: Sequence) -> np.ndarray:
    n = len(keys)
    return np.array([[0.0 if keys[i] == keys[j] else 1.0 for j in range(n)] for i in range(n)])


def model_rdms(items: Sequence[Item]) -> Dict[str, np.ndarray]:
    played = [i for i in items if i.played]
    units = [_units(i) for i in played]
    out = {m: _cosine_rdm([u[m] for u in units]) for m in
           ["motor_elements", "motor_chunk_aligned", "motor_chunk_misal", "musical_chunk",
            "abs_pitch", "intervals", "contour"]}
    out["sequence_sound"] = _identity_rdm([i.pitches for i in played])
    out["sequence_movement"] = _identity_rdm([tuple((p.string, p.fret) for p in i.positions) for i in played])
    out["sequence_fret_pattern"] = _identity_rdm([tuple((p.fret, p.finger) for p in i.positions) for i in played])
    return out


def _upper(M: np.ndarray) -> np.ndarray:
    return M[np.triu_indices(M.shape[0], k=1)]


def correlation_report(items: Sequence[Item]) -> Dict:
    played = [i for i in items if i.played]
    rdms = model_rdms(items)
    n = len(played)
    corr = np.full((len(MODELS), len(MODELS)), np.nan)
    for a, b in itertools.product(range(len(MODELS)), repeat=2):
        va, vb = _upper(rdms[MODELS[a]]), _upper(rdms[MODELS[b]])
        if np.std(va) == 0 or np.std(vb) == 0:
            continue
        corr[a, b] = spearmanr(va, vb).correlation
    key = {}
    for a, b in KEY_PAIRS:
        key[(a, b)] = corr[MODELS.index(a), MODELS.index(b)]
    return dict(models=MODELS, corr=corr, key_pairs=key, n_conditions=n, n_pairs=n * (n - 1) // 2,
                items=[i.item_id for i in played])


def separability_score(rep: Dict, pairs=(("musical_chunk", "motor_chunk_misal"),
                                         ("motor_chunk_misal", "sequence_sound"),
                                         ("motor_chunk_misal", "sequence_fret_pattern"))) -> float:
    """Largest |r| over the pairs that must separate (NaN counts as 1: an undefined model is no evidence)."""
    vals = []
    for p in pairs:
        r = rep["key_pairs"].get(p, float("nan"))
        vals.append(1.0 if (r is None or math.isnan(r)) else abs(r))
    return max(vals)


def format_report(rep: Dict) -> str:
    thr = config.RDM_THRESHOLD
    lines = [f"Separability check: {rep['n_conditions']} played items, {rep['n_pairs']} item pairs, "
             f"threshold |r| < {thr}", ""]
    lines.append("Key pairs (Spearman r):")
    for (a, b), r in rep["key_pairs"].items():
        flag = "n/a (constant model)" if r is None or math.isnan(r) else ("ok" if abs(r) < thr else "ABOVE THRESHOLD")
        rs = "  nan" if r is None or math.isnan(r) else f"{r:+.2f}"
        lines.append(f"  {a:<20} vs {b:<20} r = {rs}   {flag}")
    lines.append("")
    lines.append("Full correlation matrix:")
    names = rep["models"]
    lines.append(" " * 21 + " ".join(f"{i:>5}" for i in range(len(names))))
    for i, a in enumerate(names):
        row = " ".join("  nan" if math.isnan(rep["corr"][i, j]) else f"{rep['corr'][i, j]:+.2f}" for j in range(len(names)))
        lines.append(f"{i} {a:<19} {row}")
    return "\n".join(lines)


def save_heatmap(rep: Dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = rep["models"]
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    im = ax.imshow(np.nan_to_num(rep["corr"], nan=0.0), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(names)), names, rotation=45, ha="right")
    ax.set_yticks(range(len(names)), names)
    for i in range(len(names)):
        for j in range(len(names)):
            v = rep["corr"][i, j]
            ax.text(j, i, "n/a" if math.isnan(v) else f"{v:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="Spearman r between model RDMs")
    ax.set_title(f"{rep['n_conditions']} items, {rep['n_pairs']} pairs")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
