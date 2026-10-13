"""
selection.py
=============================
Selects two parallel stimulus sets (A, B) per strand (progressions, melodies):

  1. Pool: many sequences with unique label sequences and optimal variants.
  2. Difficulty: weighted mean of z-scored PHYSICAL features -> percentile rank within the strand.
  3. Ramp: ITEMS_PER_SET target percentiles, evenly spaced (DIFFICULTY_PCT_RANGE).
  4. Per target: one set picks the candidate (in a narrow percentile window) that is farthest from
     its own items in the standardised musical feature space (farthest-point sampling -> wide range);
     the other set picks the candidate closest in feature space to that item (-> matched ranges,
     parallel forms). The leading set alternates between A and B.
  5. out_of_key_ratio is limited by a cap that rises along the ramp (config.OUT_OF_KEY_CAP).
"""

import bisect
import math
import os
import random
from typing import Dict, List, Optional, Tuple

import config
from chord_vocab import CHORD_VOCAB
from tone_vocab import TONE_VOCAB
from generate_sequences import generate_progressions, generate_melodies
from evaluate import evaluate_progression, evaluate_melody, make_rows, write_csv

PREFIX = {"progressions": "PROG", "melodies": "MEL"}


# ---------------------------------------------------------------------------
# Pool and difficulty
# ---------------------------------------------------------------------------

def build_pool(kind: str, size: Optional[int] = None, seed: int = config.SEED) -> List[Dict]:
    size = size or config.POOL_SIZE[kind]
    if kind == "progressions":
        seqs = generate_progressions(size, seed=seed, allow_fewer=True)
        return make_rows("P", seqs, CHORD_VOCAB, evaluate_progression)
    if kind == "melodies":
        seqs = generate_melodies(size, seed=seed)
        return make_rows("M", seqs, TONE_VOCAB, evaluate_melody)
    raise ValueError(kind)


def _zscores(values: List[float]) -> List[float]:
    n = len(values)
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / n) or 1.0
    return [(v - m) / sd for v in values]


def _percentile_ranks(values: List[float]) -> List[float]:
    s = sorted(values)
    n = len(s)
    return [100.0 * (bisect.bisect_left(s, v) + bisect.bisect_right(s, v)) / (2.0 * n) for v in values]


def add_difficulty(rows: List[Dict], kind: str) -> None:
    """Adds difficulty_z (weighted mean of z-scores) and difficulty_pct (0-100) in place."""
    weights = config.DIFFICULTY_FEATURES[kind]
    wsum = sum(weights.values())
    zs = {f: _zscores([r[f] for r in rows]) for f in weights}
    raw = [sum(w * zs[f][i] for f, w in weights.items()) / wsum for i in range(len(rows))]
    for r, d, p in zip(rows, raw, _percentile_ranks(raw)):
        r["difficulty_z"] = d
        r["difficulty_pct"] = p


def out_of_key_cap(kind: str, frac: float) -> Optional[float]:
    """Upper limit for out_of_key_ratio at relative position `frac` (0..1) of the ramp."""
    cap = config.OUT_OF_KEY_CAP
    if not cap or cap.get(kind) is None:
        return None
    c0, c1 = cap[kind]
    t = 1.0 if config.OUT_OF_KEY_RAMP_END <= 0 else min(1.0, frac / config.OUT_OF_KEY_RAMP_END)
    return c0 + (c1 - c0) * t


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def _canon(labels: str) -> Tuple[str, ...]:
    """Key identical for a label sequence and its reversal."""
    seq = tuple(labels.split())
    return min(seq, seq[::-1])


def _transitions(labels: str) -> frozenset:
    seq = labels.split()
    return frozenset(frozenset(pair) for pair in zip(seq, seq[1:]))


def filter_pool(rows: List[Dict]) -> List[Dict]:
    """Keeps only sequences without avoidable cost (transition mm and fingers)."""
    return [r for r in rows
            if r["var_optimality_gap_transition_mm"] <= config.VARIATION_TOLERANCE_TRANSITION_MM
            and r["var_optimality_gap_fingers"] <= config.VARIATION_TOLERANCE_FINGERS]


def _d2(u, v) -> float:
    return sum((a - b) ** 2 for a, b in zip(u, v))


def select_sets(rows: List[Dict], kind: str, n_items: int = config.ITEMS_PER_SET,
                seed: int = config.SEED) -> Tuple[List[Dict], Dict]:
    """Returns (selected rows of both sets, info). `rows` need difficulty_pct (add_difficulty)."""
    rng = random.Random(seed)
    feats = config.SELECTION_FEATURES[kind]
    Z = list(zip(*[_zscores([r[f] for r in rows]) for f in feats]))
    pct = [r["difficulty_pct"] for r in rows]
    order = sorted(range(len(rows)), key=lambda i: pct[i])
    pct_sorted = [pct[i] for i in order]

    lo, hi = config.DIFFICULTY_PCT_RANGE
    if n_items == 1:
        targets, half0 = [(lo + hi) / 2], (hi - lo) / 2
    else:
        targets = [lo + (hi - lo) * i / (n_items - 1) for i in range(n_items)]
        half0 = (hi - lo) / (n_items - 1) / 2     # half the spacing -> windows do not overlap

    canon = [_canon(r["labels"]) for r in rows]
    trans = [_transitions(r["labels"]) for r in rows]
    max_shared = config.PAIR_MAX_SHARED_TRANSITIONS[kind]
    w = config.DIFFICULTY_MATCH_WEIGHT

    used, used_canon = set(), set()
    own = {"A": [], "B": []}
    pairs = {}
    widened = 0
    slots = list(range(n_items))
    rng.shuffle(slots)

    for k, s in enumerate(slots):
        frac = s / (n_items - 1) if n_items > 1 else 1.0
        cap = out_of_key_cap(kind, frac)
        lead, follow = ("A", "B") if k % 2 == 0 else ("B", "A")
        if not own[lead]:
            score = lambda c: sum(z * z for z in Z[c])
        else:
            score = lambda c: min(_d2(Z[c], v) for v in own[lead])

        h, found = half0, None
        while True:
            a = bisect.bisect_left(pct_sorted, targets[s] - h)
            b = bisect.bisect_right(pct_sorted, targets[s] + h)
            cands = [order[j] for j in range(a, b)
                     if order[j] not in used and canon[order[j]] not in used_canon
                     and (cap is None or rows[order[j]]["out_of_key_ratio"] <= cap + 1e-9)]
            if len(cands) >= 2 and (len(cands) >= config.MIN_CANDIDATES or h > 25):
                for pick in sorted(cands, key=score, reverse=True)[:40]:
                    valid = [c for c in cands if c != pick and canon[c] != canon[pick]
                             and len(trans[c] & trans[pick]) <= max_shared]
                    if valid:
                        match = min(valid, key=lambda c: math.sqrt(_d2(Z[c], Z[pick]))
                                    + w * abs(pct[c] - pct[pick]))
                        found = (pick, match)
                        break
            if found or h > 25:
                break
            h *= 1.5
        if not found:
            raise RuntimeError(f"{kind}: no valid pair for slot {s + 1} (target percentile "
                               f"{targets[s]:.1f}, out-of-key cap {cap}). "
                               f"Enlarge the pool or relax OUT_OF_KEY_CAP / PAIR_MAX_SHARED_TRANSITIONS.")
        if h > half0:
            widened += 1
        pick, match = found
        used.update((pick, match))
        used_canon.update((canon[pick], canon[match]))
        own[lead].append(Z[pick])
        own[follow].append(Z[match])
        pairs[s] = (pick, match) if lead == "A" else (match, pick)

    ordered = sorted(pairs.values(), key=lambda ab: (pct[ab[0]] + pct[ab[1]]) / 2)
    selected = []
    for pos, (ia, ib) in enumerate(ordered, start=1):
        for set_name, idx in (("A", ia), ("B", ib)):
            r = rows[idx]
            row = dict(stimulus_id=f"{PREFIX[kind]}-{set_name}-{pos:02d}", set=set_name, position=pos,
                       pool_id=r["id"], difficulty_pct=r["difficulty_pct"], difficulty_z=r["difficulty_z"])
            row.update({k2: v for k2, v in r.items() if k2 not in ("id", "difficulty_pct", "difficulty_z")})
            selected.append(row)
    return selected, dict(widened_slots=widened)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def selection_report(kind: str, pool: List[Dict], selected: List[Dict], info: Dict) -> str:
    feats = list(config.SELECTION_FEATURES[kind])
    if "out_of_key_ratio" not in feats:
        feats.append("out_of_key_ratio")      # reported, but limited by the cap instead of maximised
    A = sorted((r for r in selected if r["set"] == "A"), key=lambda r: r["position"])
    B = sorted((r for r in selected if r["set"] == "B"), key=lambda r: r["position"])
    rng_ = lambda rs, f: f"{min(r[f] for r in rs):.2f} - {max(r[f] for r in rs):.2f}"
    out = [f"=== {kind}: pool {len(pool)} sequences (of {info['raw_pool']} generated), {len(A)} items per set ===",
           f"{'feature':<28}{'pool range':>18}{'set A':>18}{'set B':>18}"]
    for f in feats:
        out.append(f"{f:<28}{rng_(pool, f):>18}{rng_(A, f):>18}{rng_(B, f):>18}")
    d = [abs(a["difficulty_pct"] - b["difficulty_pct"]) for a, b in zip(A, B)]
    inv = lambda rs: sum(1 for x, y in zip(rs, rs[1:]) if y["difficulty_pct"] < x["difficulty_pct"])
    out.append(f"difficulty percentile: A {A[0]['difficulty_pct']:.1f} -> {A[-1]['difficulty_pct']:.1f}, "
               f"B {B[0]['difficulty_pct']:.1f} -> {B[-1]['difficulty_pct']:.1f}")
    out.append(f"|A_i - B_i| in percentile points: mean {sum(d) / len(d):.2f}, max {max(d):.2f}; "
               f"order inversions: A {inv(A)}, B {inv(B)}; widened windows: {info['widened_slots']}")
    n = len(A)
    for name, rs in (("A", A), ("B", B)):
        thirds = [rs[:n // 3], rs[n // 3: 2 * n // 3], rs[2 * n // 3:]]
        share = " / ".join(f"{sum(1 for r in t if r['out_of_key_ratio'] > 0) / len(t):.0%}" for t in thirds)
        out.append(f"set {name}: share with out-of-key elements by third of the ramp: {share}")
    out.append(f"unique label sequences among selected: {len({r['labels'] for r in selected})} of {len(selected)}")
    fp = sum(1 for r in selected if r["var_unnecessary_ratio_fingers"] > 0 or r["var_unnecessary_ratio_transition"] > 0)
    out.append(f"selected items with avoidable variation cost (transition or fingers): {fp} of {len(selected)}")
    return "\n".join(out)


def run_selection(save_pool: bool = False, seed: int = config.SEED,
                  out_dir: str = config.STIMULI_DIR) -> Dict[str, List[Dict]]:
    result, reports = {}, []
    for kind in ("progressions", "melodies"):
        raw = build_pool(kind, seed=seed)
        pool = filter_pool(raw) if config.REQUIRE_NO_AVOIDABLE_COST else raw
        add_difficulty(pool, kind)
        if save_pool:
            write_csv(os.path.join(out_dir, f"pool_{kind}.csv"), pool)
        selected, info = select_sets(pool, kind, seed=seed)
        info["raw_pool"] = len(raw)
        write_csv(os.path.join(out_dir, f"selected_{kind}.csv"), selected)
        reports.append(selection_report(kind, pool, selected, info))
        result[kind] = selected
    text = "\n\n".join(reports)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "selection_report.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    return result