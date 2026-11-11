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
  C-VIII  collinearity of the combination components (sound, movement, interaction, structure) over E2: each
      component regressed on the others (on ranks, matching the Spearman correlations); multiple R and variance
      inflation factor (VIF). "Threshold as for |r|" (build spec section 8) is read as multiple R < RDM_THRESHOLD,
      i.e. VIF < 1 / (1 - RDM_THRESHOLD^2) (1.10 for 0.3).
  Reports without optimization (build spec section 8): r(finger, fret), r(string, absolute pitch) over the played
      items (M-IV); r(absolute pitch, scale degree), r(interval size, musical boundary), the A-IV split
      (concrete / relational / tonal) and the variance of the interval and contour RDMs over all heard items,
      listen-only probes included (A-IV).
All models are listed in analysis/models.py. Target |r| < config.RDM_THRESHOLD.

How a correlation between two models is computed: build both RDMs over the same items, take the values above the
diagonal (one value per item pair, _upper), and correlate them with Spearman's r. |r| near 0 = the two models predict
different similarity patterns, so the data can tell them apart; |r| near 1 = they predict the same pattern.
If a model is constant over the items (every pair equally different), r is undefined (NaN) and counts as 1 in the
scores: a constant model gives no evidence of separability.
"""

import itertools
import math
from typing import Dict, Optional, Sequence

import numpy as np
from scipy.stats import rankdata, spearmanr

from ukustim import config
from ukustim.analysis import models as md
from ukustim.core.items import Item

# which variant types enter each evaluation set (listen-only probes never do)
E1_VARIANTS = ("base", "alternate fingering", "recombined", "mixed", "new-chunk")
E2_VARIANTS = ("base", "alternate fingering", "string-pair shift", "played transposition")

# model pairs that MUST separate (they define the E1 / E2 scores)
PAIRS_E1 = [("musical_chunk", "motor_chunk_misal_full"),
            ("musical_chunk", "motor_chunk_misal_lh"),
            ("motor_chunk_misal_lh", "concrete_sound"),
            ("motor_chunk_misal_lh", "movement_graded")]
PAIRS_E2 = [("movement_identity", "concrete_sound"),
            ("movement_identity", "abstract_structure"),
            ("concrete_sound", "abstract_structure")]
# report-only pairs: nuisance models vs chunk models, and extra analysis contrasts shown under E1
CHUNK_MODELS = ["musical_chunk", "motor_chunk_misal_lh"]
PAIRS_NUISANCE = [(n, c) for n in md.NUISANCE_MODELS for c in CHUNK_MODELS]
PAIRS_EXTRA = [("motor_chunk_misal_lh", "movement_identity"),   # identity is sparse in early bands (Q8): often constant on E1
               ("motor_chunk_misal_lh", "motor_chunk_aligned_lh"), ("musical_chunk", "motor_chunk_aligned_lh"),
               ("musical_chunk", "motor_chunk_crossing_lh")]


# 'reports without optimization' (build spec v1.7, section 8)
M4_PAIRS = [("finger", "fret"), ("string", "abs_pitch")]
A4_PAIRS = [("abs_pitch", "scale_degree"), ("interval_size", "musical_boundary"),
            ("abs_pitch", "intervals"), ("abs_pitch", "contour"), ("intervals", "scale_degree"),
            ("contour", "scale_degree")]
A4_VARIANCE_MODELS = ["intervals", "contour"]


def _upper(M: np.ndarray) -> np.ndarray:
    """Values above the diagonal of an RDM: one per item pair (the matrix is symmetric, the diagonal is 0)."""
    return M[np.triu_indices(M.shape[0], k=1)]


def _corr(va: np.ndarray, vb: np.ndarray) -> float:
    """Spearman r between two vectors of pair values; NaN if fewer than 3 pairs or either vector is constant."""
    if len(va) < 3 or np.std(va) == 0 or np.std(vb) == 0:
        return float("nan")
    return float(spearmanr(va, vb).correlation)


def _subset(items: Sequence[Item], variants) -> list:
    """Played items of the given variant types (an evaluation set)."""
    return [i for i in items if i.played and i.variant_type in variants]


def pair_correlations(items: Sequence[Item], pairs) -> Dict[tuple, float]:
    """{(model_a, model_b): Spearman r} over the given items, computing each needed RDM once."""
    names = sorted({m for p in pairs for m in p})
    rdms = md.model_rdms(items, names)
    return {(a, b): _corr(_upper(rdms[a]), _upper(rdms[b])) for a, b in pairs}


def collinearity(items: Sequence[Item], components: Sequence[str] = None) -> Dict:
    """Multiple R and VIF of each component regressed on the others (ranks of the upper-triangle RDM values),
    plus pairwise Spearman r, over the given items (normally E2, the played family members)."""
    components = list(components or md.C8_COMPONENTS)
    rdms = md.model_rdms(items, components)
    X = {c: _upper(rdms[c]) for c in components}
    comp_out = {}
    for c in components:
        y = X[c]
        others = [X[o] for o in components if o != c and np.std(X[o]) > 0]
        if len(y) < 3 or np.std(y) == 0:
            comp_out[c] = dict(R=float("nan"), vif=float("nan"))
            continue
        # ordinary least squares on ranks: y ~ intercept + the other components; R^2 = explained variance
        yr = rankdata(y)
        A = np.column_stack([rankdata(o) for o in others] + [np.ones(len(y))])
        coef, *_ = np.linalg.lstsq(A, yr, rcond=None)
        r2 = 1 - np.sum((yr - A @ coef) ** 2) / np.sum((yr - yr.mean()) ** 2)
        r2 = min(max(r2, 0.0), 1.0)
        # VIF = 1 / (1 - R^2): 1 = independent of the others, large = predictable from them
        comp_out[c] = dict(R=math.sqrt(r2), vif=float(1 / (1 - r2)) if r2 < 1 - 1e-12 else float("inf"))
    pairs = {(a, b): _corr(X[a], X[b]) for a, b in itertools.combinations(components, 2)}
    return dict(n_conditions=len([i for i in items if i.played]), components=comp_out, pairs=pairs)


def score_c8_of(col: Dict) -> float:
    """Largest multiple R over the C-VIII components (undefined = 1)."""
    return max((1.0 if math.isnan(v["R"]) else v["R"]) for v in col["components"].values())


def descriptive_reports(items: Sequence[Item]) -> Dict:
    """Build spec section 8, 'reports without optimization': M-IV over played items, A-IV over all heard items."""
    played = [i for i in items if i.played]
    m4 = pair_correlations(played, M4_PAIRS)
    names = sorted({m for p in A4_PAIRS for m in p} | set(A4_VARIANCE_MODELS))
    rdms = md.model_rdms(items, names, include_listen_only=True)
    a4 = {(a, b): _corr(_upper(rdms[a]), _upper(rdms[b])) for a, b in A4_PAIRS}
    var = {m: dict(variance=float(np.var(_upper(rdms[m]))), distinct=int(len(np.unique(np.round(_upper(rdms[m]), 9)))))
           for m in A4_VARIANCE_MODELS}
    return dict(n_played=len(played), n_heard=len(items), m4=m4, a4=a4, a4_variance=var)


def report(items: Sequence[Item]) -> Dict:
    """Full separability report: evaluation sets E1 and E2, nuisance correlations, C-VIII collinearity, descriptive
    M-IV / A-IV reports, full matrix over all played items."""
    e1, e2 = _subset(items, E1_VARIANTS), _subset(items, E2_VARIANTS)
    played = [i for i in items if i.played]
    # model x model correlation matrix over all played items (for rdm_correlations.png)
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
        nuisance=pair_correlations(e1, PAIRS_NUISANCE),
        c8=collinearity(e2, md.C8_COMPONENTS), c8_product=collinearity(e2, md.C8_COMPONENTS_PRODUCT),
        descriptive=descriptive_reports(items))


def _worst(pairs: Dict[tuple, float], wanted) -> float:
    """Largest |r| over the wanted pairs (undefined = 1: a constant model is no evidence of separability)."""
    return max((1.0 if math.isnan(pairs[p]) else abs(pairs[p])) for p in wanted)


def score_e1(rep: Dict) -> float:
    """E1 score of a full report: worst |r| over PAIRS_E1."""
    return _worst(rep["e1"]["pairs"], PAIRS_E1)


def score_e2(rep: Dict) -> float:
    """E2 score of a full report: worst |r| over PAIRS_E2 (and the C-VIII multiple R if E2_INCLUDES_C8)."""
    s = _worst(rep["e2"]["pairs"], PAIRS_E2)
    return max(s, score_c8_of(rep["c8"])) if config.E2_INCLUDES_C8 else s


def score_c8(rep: Dict) -> float:
    """Largest C-VIII multiple R of a full report."""
    return score_c8_of(rep["c8"])


def scores(items: Sequence[Item]):
    """(E1 score, E2 score): worst |r| over the pairs that must separate in each evaluation set. With
    config.E2_INCLUDES_C8 the E2 score is also at least the largest multiple R of the C-VIII components. Computes
    only the models it needs, so it is cheap enough for the search."""
    e1, e2 = _subset(items, E1_VARIANTS), _subset(items, E2_VARIANTS)
    s2 = _worst(pair_correlations(e2, PAIRS_E2), PAIRS_E2)
    if config.E2_INCLUDES_C8:
        s2 = max(s2, score_c8_of(collinearity(e2, md.C8_COMPONENTS)))
    return _worst(pair_correlations(e1, PAIRS_E1), PAIRS_E1), s2


def objective(items: Sequence[Item]) -> float:
    """Search objective (lower is better): the E1 score, with the E2 score as a smaller second term.
    The search computes the same formula itself in objective_search.evaluate (with the penalties added)."""
    s1, s2 = scores(items)
    return s1 + 0.2 * s2


def _fmt(r: float, thr: float) -> str:
    """'r   ok' / 'r   ABOVE THRESHOLD' / 'nan n/a' for the report."""
    if math.isnan(r):
        return "  nan   n/a (constant model)"
    return f"{r:+.2f}   {'ok' if abs(r) < thr else 'ABOVE THRESHOLD'}"


def format_report(rep: Dict) -> str:
    """The separability part of report.txt, in this order: E1, E2, nuisance, C-VIII (both interaction forms),
    descriptive M-IV / A-IV reports, the section 8a table."""
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
    vif_max = 1 / (1 - thr ** 2)
    for key, title in (("c8", "C-VIII components (E2): collinearity, each regressed on the others"),
                       ("c8_product", "C-VIII, alternative interaction 1 - s_sound x s_move")):
        col = rep[key]
        lines += ["", f"{title}; target multiple R < {thr} (VIF < {vif_max:.2f}); {col['n_conditions']} items"
                  + ("" if key == "c8" or config.E2_INCLUDES_C8 is False else "   (report only)")]
        for c, v in col["components"].items():
            if math.isnan(v["R"]):
                lines.append(f"  {c:<26} constant (n/a)")
            else:
                ok = "ok" if v["R"] < thr else "ABOVE THRESHOLD"
                lines.append(f"  {c:<26} R = {v['R']:.2f}   VIF = {v['vif']:.2f}   {ok}")
        if key == "c8":
            for (a, b), r in col["pairs"].items():
                lines.append(f"    {a:<24} vs {b:<24} r = {_fmt(r, thr)}")
    d = rep["descriptive"]
    lines += ["", f"Reports without optimization (build spec section 8):",
              f"  M-IV, over the {d['n_played']} played items:"]
    for (a, b), r in d["m4"].items():
        lines.append(f"    {a:<22} vs {b:<22} r = {'n/a' if math.isnan(r) else f'{r:+.2f}'}")
    lines.append(f"  A-IV, over all {d['n_heard']} heard items (listen-only probes included):")
    for (a, b), r in d["a4"].items():
        lines.append(f"    {a:<22} vs {b:<22} r = {'n/a' if math.isnan(r) else f'{r:+.2f}'}")
    for m, v in d["a4_variance"].items():
        lines.append(f"    variance of the {m} RDM: {v['variance']:.4f} ({v['distinct']} distinct distances)")
    lines += ["", "Models and the research questions they serve (build spec section 8a):"]
    for models_, serves, sep_from in md.MODEL_SERVES:
        lines.append(f"  {serves:<22} {models_:<62} must separate from: {sep_from}")
    lines += ["", f"Full correlation matrix over all {rep['all']['n_conditions']} played items "
                  f"({rep['all']['n_pairs']} pairs); see rdm_correlations.png"]
    return "\n".join(lines)


def save_heatmap(rep: Dict, path: str) -> None:
    """rdm_correlations.png: the model x model Spearman matrix over all played items, with the values printed."""
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
