"""
separability.py
=============================
Separability check of a finished set (build spec section 8): Spearman correlations between model RDMs, over the
evaluation sets the spec names, plus the scores used as the objective of the set search.

  E1  musical chunk vs motor chunk: bases, alternate fingerings and generalization items
      (string-pair shifts, transpositions and probes are excluded: their chunks are new in both models by
      construction, which inflates the correlation)
  E2  three-level contrasts: all played family members (base, alternate fingering, string-pair shift,
      played transposition)
  Nuisance models (scale degree, phrase position, beat x degree) are correlated with the chunk models on E1.
All models are listed in analysis/models.py. Target |r| < config.RDM_THRESHOLD.
"""

import itertools
import math
from typing import Dict, Optional, Sequence

import numpy as np
from scipy.stats import spearmanr

from ukustim import config
from ukustim.analysis import models as md
from ukustim.core.items import Item

E1_VARIANTS = ("base", "alternate fingering", "recombined", "mixed", "new-chunk")
E2_VARIANTS = ("base", "alternate fingering", "string-pair shift", "played transposition")

PAIRS_E1 = [("musical_chunk", "motor_chunk_misal_full"),
            ("musical_chunk", "motor_chunk_misal_lh"),
            ("motor_chunk_misal_lh", "concrete_sound"),
            ("motor_chunk_misal_lh", "movement_graded")]
PAIRS_E2 = [("movement_identity", "concrete_sound"),
            ("movement_identity", "abstract_structure"),
            ("concrete_sound", "abstract_structure")]
CHUNK_MODELS = ["musical_chunk", "motor_chunk_misal_lh"]
PAIRS_NUISANCE = [(n, c) for n in md.NUISANCE_MODELS for c in CHUNK_MODELS]
PAIRS_EXTRA = [("motor_chunk_misal_lh", "movement_identity"),   # identity is sparse in early bands (Q8): often constant on E1
               ("motor_chunk_misal_lh", "motor_chunk_aligned_lh"), ("musical_chunk", "motor_chunk_aligned_lh"),
               ("musical_chunk", "motor_chunk_crossing_lh")]


def _upper(M: np.ndarray) -> np.ndarray:
    return M[np.triu_indices(M.shape[0], k=1)]


def _corr(va: np.ndarray, vb: np.ndarray) -> float:
    if len(va) < 3 or np.std(va) == 0 or np.std(vb) == 0:
        return float("nan")
    return float(spearmanr(va, vb).correlation)


def _subset(items: Sequence[Item], variants) -> list:
    return [i for i in items if i.played and i.variant_type in variants]


def pair_correlations(items: Sequence[Item], pairs) -> Dict[tuple, float]:
    names = sorted({m for p in pairs for m in p})
    rdms = md.model_rdms(items, names)
    return {(a, b): _corr(_upper(rdms[a]), _upper(rdms[b])) for a, b in pairs}


def report(items: Sequence[Item]) -> Dict:
    """Full separability report: evaluation sets E1 and E2, nuisance correlations, full matrix over all played items."""
    e1, e2 = _subset(items, E1_VARIANTS), _subset(items, E2_VARIANTS)
    played = [i for i in items if i.played]
    rdms = md.model_rdms(played)
    k = len(md.MODELS)
    corr = np.full((k, k), np.nan)
    for a, b in itertools.product(range(k), repeat=2):
        corr[a, b] = _corr(_upper(rdms[md.MODELS[a]]), _upper(rdms[md.MODELS[b]]))
    n = lambda xs: dict(n_conditions=len(xs), n_pairs=len(xs) * (len(xs) - 1) // 2, items=[i.item_id for i in xs])
    return dict(
        models=md.MODELS, corr=corr, all=n(played),
        e1=dict(n(e1), pairs=pair_correlations(e1, PAIRS_E1 + PAIRS_EXTRA)),
        e2=dict(n(e2), pairs=pair_correlations(e2, PAIRS_E2)),
        nuisance=pair_correlations(e1, PAIRS_NUISANCE))


def _worst(pairs: Dict[tuple, float], wanted) -> float:
    """Largest |r| over the wanted pairs (undefined = 1: a constant model is no evidence of separability)."""
    return max((1.0 if math.isnan(pairs[p]) else abs(pairs[p])) for p in wanted)


def score_e1(rep: Dict) -> float:
    return _worst(rep["e1"]["pairs"], PAIRS_E1)


def score_e2(rep: Dict) -> float:
    return _worst(rep["e2"]["pairs"], PAIRS_E2)


def scores(items: Sequence[Item]):
    """(E1 score, E2 score): worst |r| over the pairs that must separate in each evaluation set. Computes only the
    models it needs, so it is cheap enough for the search."""
    e1, e2 = _subset(items, E1_VARIANTS), _subset(items, E2_VARIANTS)
    return (_worst(pair_correlations(e1, PAIRS_E1), PAIRS_E1),
            _worst(pair_correlations(e2, PAIRS_E2), PAIRS_E2))


def objective(items: Sequence[Item]) -> float:
    """Search objective (lower is better): the E1 score, with the E2 score as a smaller second term."""
    s1, s2 = scores(items)
    return s1 + 0.2 * s2


def _fmt(r: float, thr: float) -> str:
    if math.isnan(r):
        return "  nan   n/a (constant model)"
    return f"{r:+.2f}   {'ok' if abs(r) < thr else 'ABOVE THRESHOLD'}"


def format_report(rep: Dict) -> str:
    thr = config.RDM_THRESHOLD
    lines = [f"Separability check, target |r| < {thr}", ""]
    for key, title, wanted in (("e1", "E1: musical chunk vs motor chunk (bases, alternate fingerings, generalization items)",
                                PAIRS_E1),
                               ("e2", "E2: three levels (base, alternate fingering, string-pair shift, played transposition)",
                                PAIRS_E2)):
        e = rep[key]
        lines.append(f"{title}: {e['n_conditions']} items, {e['n_pairs']} item pairs")
        for (a, b), r in e["pairs"].items():
            tag = "" if (a, b) in wanted else "   (analysis contrast)"
            lines.append(f"  {a:<24} vs {b:<24} r = {_fmt(r, thr)}{tag}")
        lines.append("")
    lines.append("Nuisance models vs chunk models (E1; report only, chunk models must not be explained by them):")
    for (a, b), r in rep["nuisance"].items():
        lines.append(f"  {a:<24} vs {b:<24} r = {_fmt(r, thr)}")
    lines += ["", f"Full correlation matrix over all {rep['all']['n_conditions']} played items "
                  f"({rep['all']['n_pairs']} pairs); see rdm_correlations.png"]
    return "\n".join(lines)


def save_heatmap(rep: Dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = rep["models"]
    fig, ax = plt.subplots(figsize=(11, 9.5))
    im = ax.imshow(np.nan_to_num(rep["corr"], nan=0.0), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(names)), names, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(names)), names, fontsize=8)
    for i in range(len(names)):
        for j in range(len(names)):
            v = rep["corr"][i, j]
            ax.text(j, i, "n/a" if math.isnan(v) else f"{v:.1f}", ha="center", va="center", fontsize=5)
    fig.colorbar(im, ax=ax, label="Spearman r between model RDMs", shrink=0.7)
    ax.set_title(f"All played items: {rep['all']['n_conditions']} items, {rep['all']['n_pairs']} pairs")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
