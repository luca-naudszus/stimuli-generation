"""
exact_cover.py
=============================
Set search for the minimal case (3 bases, 6 trained chunks, every chunk in exactly 2 bases):
random chunk subsets (find_sets) and exhaustive enumeration of exact-cover triples (find_sets_exhaustive).
The objective-driven search for 3-6 bases is in objective_search.py.
"""

import itertools
import random
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

from ukustim import config
from ukustim.core import versions as vs
from ukustim.core.fingering import positions_of, valid_assignments
from ukustim.core.inventory import Inventory
from ukustim.selection.solution import Solution, turning_cap_ok

Chunk = Tuple[int, ...]


# ---------------------------------------------------------------------------
# Tier 2: prototype set search
# ---------------------------------------------------------------------------

def _grow_subset(inv: Inventory, rng: random.Random, size: int) -> List[Chunk]:
    start = rng.choice(inv.chunks)
    P = [start]
    while len(P) < size:
        pool = {x for c in P for x in inv.graph[c] + inv.preds[c]} - set(P)
        if not pool:
            return []
        P.append(rng.choice(sorted(pool)))
    return P


def _orders_within(inv: Inventory, P: Sequence[Chunk]) -> List[Tuple[Chunk, ...]]:
    Pset = set(P)
    out = []

    def rec(prefix):
        if len(prefix) == config.N_CHUNKS:
            out.append(tuple(prefix))
            return
        for nxt in inv.graph[prefix[-1]]:
            if nxt in Pset and nxt not in prefix:
                prefix.append(nxt)
                rec(prefix)
                prefix.pop()

    for c in P:
        rec([c])
    return out


def _covers(orders, P, n_bases, rng, cap=300):
    """Random combinations of n_bases chunk orders in which every chunk of P is used >= 2 times."""
    if len(orders) < n_bases:
        return
    seen = 0
    tries = 0
    while seen < cap and tries < cap * 20:
        tries += 1
        combo = rng.sample(orders, n_bases)
        cnt = Counter(c for t in combo for c in t)
        if set(cnt) == set(P) and min(cnt.values()) >= 2:
            seen += 1
            yield combo


def _share_ok(motor_ids: List[set], crossing_ids: List[set]) -> bool:
    for i in range(len(motor_ids)):
        others = set().union(*[motor_ids[j] for j in range(len(motor_ids)) if j != i])
        if not (crossing_ids[i] & others):
            return False
    return True


def _try_cover(inv: Inventory, combo, P, deg, rng) -> Optional[Solution]:
    if not turning_cap_ok(P):
        return None
    comps = vs.misaligned_compositions(deg)
    # fingering per chunk of P (product of option indices)
    ranges = [range(len(inv.opts[c])) for c in P]
    prod = list(itertools.product(*ranges))
    rng.shuffle(prod)
    prod.sort(key=lambda a: sum(1 for x in a if x))      # prefer the default (lowest-fret) fingering; stable after shuffle
    for assign in prod[:200]:
        f = dict(zip(P, assign))
        per_base = []
        for t in combo:
            good = []
            for comp in comps:
                a = next(valid_assignments(t, comp, inv.opts, fixed=f), None)
                if a is not None:
                    good.append(comp)
            if not good:
                break
            per_base.append(good)
        else:
            choices = list(itertools.product(*per_base))
            rng.shuffle(choices)
            for pick in choices[:200]:
                motor, cross = [], []
                for t, comp in zip(combo, pick):
                    pos = positions_of(t, tuple(f[c] for c in t), inv.opts)
                    motor.append({m for _, _, m in vs.motor_chunks(pos, comp)})
                    cross.append(vs.crossing_motor_ids(pos, comp))
                if _share_ok(motor, cross):
                    return Solution(deg, list(P), f, list(zip(combo, pick)))
    return None


def find_sets(inv: Inventory, deg: int, trials: Optional[int] = None, seed: Optional[int] = None,
              n_bases: Optional[int] = None, n_trained: Optional[int] = None,
              want: int = 10) -> Tuple[List[Solution], Dict]:
    trials = config.SEARCH_TRIALS if trials is None else trials
    rng = random.Random(config.SEED if seed is None else seed)
    n_bases = config.N_BASES if n_bases is None else n_bases
    n_trained = config.N_TRAINED_CHUNKS if n_trained is None else n_trained
    sols: List[Solution] = []
    stats = Counter()
    seen_sets = set()
    for _ in range(trials):
        stats["trials"] += 1
        P = _grow_subset(inv, rng, n_trained)
        if not P:
            continue
        key = frozenset(P)
        if key in seen_sets:
            stats["repeated_subset"] += 1
            continue
        seen_sets.add(key)
        orders = _orders_within(inv, P)
        if len(orders) < n_bases:
            stats["too_few_orders"] += 1
            continue
        found = None
        for combo in _covers(orders, P, n_bases, rng, cap=60):
            stats["covers_tried"] += 1
            found = _try_cover(inv, combo, P, deg, rng)
            if found:
                break
        if found:
            stats["subsets_with_solution"] += 1
            sols.append(found)
            if len(sols) >= want:
                break
    stats["distinct_subsets"] = len(seen_sets)
    return sols, dict(stats)


# ---------------------------------------------------------------------------
# Exhaustive enumeration for the exact case (N_BASES = 3, N_TRAINED_CHUNKS = 6: every chunk in exactly 2 bases)
# ---------------------------------------------------------------------------

def valid_orders(inv: Inventory, deg: int) -> List[Tuple[Chunk, ...]]:
    comps = vs.misaligned_compositions(deg)
    out = []
    for t in inv.tuples:
        if any(next(valid_assignments(t, comp, inv.opts), None) is not None for comp in comps):
            out.append(t)
    return out


def exact_triples(orders: Sequence[Tuple[Chunk, ...]]) -> List[Tuple[Tuple[Chunk, ...], ...]]:
    """All unordered triples of chunk orders A, B, C with |A u B u C| = 6 and every chunk in exactly two of them."""
    idx = {o: i for i, o in enumerate(orders)}
    sets = [frozenset(o) for o in orders]
    by_set: Dict[frozenset, List[int]] = {}
    for i, s in enumerate(sets):
        by_set.setdefault(s, []).append(i)
    by_pair: Dict[frozenset, List[int]] = {}
    for i, o in enumerate(orders):
        for p in itertools.combinations(sorted(set(o)), 2):
            by_pair.setdefault(frozenset(p), []).append(i)
    out = []
    for i, o in enumerate(orders):
        for p in itertools.combinations(sorted(set(o)), 2):
            for j in by_pair[frozenset(p)]:
                if j <= i or len(sets[i] & sets[j]) != 2:
                    continue
                rest = (sets[i] | sets[j]) - (sets[i] & sets[j])
                for k in by_set.get(rest, []):
                    if k > j:
                        out.append((orders[i], orders[j], orders[k]))
    return list(dict.fromkeys(out))


def find_sets_exhaustive(inv: Inventory, deg: int, max_tries: int = 3000, want: int = 15,
                         seed: int = 0) -> Tuple[List[Solution], Dict]:
    """Enumerate all exact-cover triples of valid chunk orders, then test fingering / composition / sharing."""
    rng = random.Random(config.SEED + 77 + seed)
    orders = valid_orders(inv, deg)
    triples = exact_triples(orders)
    stats = dict(valid_orders=len(orders), exact_triples=len(triples), tried=0, feasible=0)
    rng.shuffle(triples)
    sols: List[Solution] = []
    seen = set()
    for trip in triples[:max_tries]:
        P = sorted({c for t in trip for c in t})
        stats["tried"] += 1
        sol = _try_cover(inv, list(trip), P, deg, rng)
        if sol:
            stats["feasible"] += 1
            sols.append(sol)
            if len(sols) >= want:
                break
    return sols, stats
