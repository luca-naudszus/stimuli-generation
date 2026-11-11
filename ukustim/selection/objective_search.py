"""
objective_search.py
=============================
Set search with the separability score as the objective (build spec sections 3, 4, 8; Q7), for 3 to 6 bases.

1. Sample feasible sets: K valid bases (chunk order + composition + fingering, enumerated up front) whose shared
   chunks have the same fingering, every chunk in >= 2 bases, at most N trained chunks, minimum recurrence.
2. Evaluate a set by building its whole family (alternate fingering, shift, transposition, recombined, mixed,
   new-chunk items) and computing the objective of analysis/separability.py (worst |r| over the pairs that must
   separate; smaller is better). Missing family members add a penalty.
3. Local moves on the best sets: replace one base by another valid base that fits the rest of the set
   (same fingering for shared chunks, within N trained chunks).

Time-boxed (config.SEARCH_BUDGET_S per degree and number of bases). Results are random-restart local search,
not proofs of optimality; two runs can differ by about 0.1 in E1.

Score of a set (lower is better):
    objective = E1 + 0.2 * E2      (E1, E2 = worst |r| over the model pairs that must separate; analysis/separability)
    score     = objective + missing_penalty(notes) - COMP_VARIETY_BONUS * (number of distinct compositions)
The penalty weights below are implementation choices, not spec values; they only rank sets.
Called by cli.cmd_search once per (degree, number of bases).
"""

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ukustim import config
from ukustim.analysis import separability as sep
from ukustim.core import chunks as ch
from ukustim.core import versions as vs
from ukustim.core.fingering import positions_of, valid_assignments
from ukustim.core.inventory import Inventory
from ukustim.core.items import Item, Registry
from ukustim.family.transposition import has_transposition
from ukustim.selection import exact_cover as ec
from ukustim.selection.assemble import assemble_family
from ukustim.selection.solution import Solution, turning_cap_ok

# Penalties for family members that could not be built (added to the objective, which is a worst |r| in 0..1):
PENALTY_PER_BASE_WITHOUT_ALTERNATE = 0.15    # alternate fingering and string-pair shift are expected for every base
PENALTY_PER_BASE_WITHOUT_SHIFT = 0.15
PENALTY_TRANSPOSITION = 0.1                  # times the share of bases without a played transposition
PENALTY_PER_MISSING_GENERALIZATION = 0.05    # recombined (3 types), mixed, new-chunk items
COMP_VARIETY_BONUS = 0.01                    # per distinct composition among the bases (build spec Q7, step 3)


def missing_penalty(notes: Sequence[str], n_bases: int) -> float:
    """Penalty from the assembly notes (assemble_family records what it could not build). Notes about one base start
    with its ID ('B3: ...'); all other notes are about missing generalization items."""
    alt = sum("no valid alternate" in n for n in notes)
    shift = sum("string-pair shift impossible" in n for n in notes)
    trans = sum("played transposition" in n for n in notes)
    other = sum(1 for n in notes if not n.startswith("B"))
    return (PENALTY_PER_BASE_WITHOUT_ALTERNATE * alt + PENALTY_PER_BASE_WITHOUT_SHIFT * shift
            + PENALTY_TRANSPOSITION * trans / max(n_bases, 1) + PENALTY_PER_MISSING_GENERALIZATION * other)


@dataclass
class Evaluated:
    """A set after evaluation: the solution, its full item list and registry, the assembly notes and the scores."""
    score: float
    solution: Solution
    items: List[Item]
    registry: Registry
    notes: List[str]
    objective: float = 0.0
    e1: float = 1.0
    e2: float = 1.0


def feasible(inv: Inventory, sol: Solution) -> bool:
    """Neutrality and span for every base with the chosen fingering, every chunk in >= 2 bases, distinct orders,
    minimum recurrence (every base shares a crossing motor chunk with another base)."""
    # musical side: distinct orders, every chunk used at least twice, turning-point cap
    orders = [t for t, _ in sol.bases]
    if len(set(orders)) != len(orders):
        return False
    cnt: Dict[Tuple[int, ...], int] = {}
    for t in orders:
        for c in t:
            cnt[c] = cnt.get(c, 0) + 1
    if set(cnt) != set(sol.chunks) or min(cnt.values()) < 2 or not turning_cap_ok(sol.chunks):
        return False
    # motor side: every base neutral with the set's fingering (all chunks pinned = a yes / no check), then recurrence
    motor, cross = [], []
    for t, comp in sol.bases:
        if vs.degree(comp) != sol.degree:
            return False
        a = next(valid_assignments(t, comp, inv.opts, fixed=sol.fingering), None)
        if a is None:
            return False
        pos = positions_of(t, tuple(sol.fingering[c] for c in t), inv.opts)
        motor.append({m for _, _, m in vs.motor_chunks(pos, comp)})
        cross.append(vs.crossing_motor_ids(pos, comp))
    return ec._share_ok(motor, cross)


def evaluate(inv: Inventory, sol: Solution, alt_combos: int = 400, seed: int = 0) -> Evaluated:
    """Build the set's whole family and score it (see module docstring). This is the expensive step of the search:
    every evaluation assembles all family members and computes the E1 / E2 correlations."""
    items, reg, notes = assemble_family(inv, sol, seed=seed, alt_combos=alt_combos)
    e1, e2 = sep.scores(items)
    obj = e1 + 0.2 * e2
    comps = {comp for _, comp in sol.bases}
    score = obj + missing_penalty(notes, len(sol.bases)) - COMP_VARIETY_BONUS * len(comps)
    return Evaluated(score, sol, items, reg, notes, obj, e1, e2)


@dataclass(frozen=True)
class Cand:
    """One valid base: chunk order, misaligned composition and the fingering option of each of its chunks."""
    order: Tuple[Tuple[int, ...], ...]
    comp: Tuple[int, ...]
    assign: Tuple[int, ...]
    transposable: bool = False      # a played transposition to config.TRANSPOSITION_KEY exists for this base

    def fing(self) -> Dict[Tuple[int, ...], int]:
        """chunk -> fingering option index, for this base's chunks."""
        return dict(zip(self.order, self.assign))


def candidates(inv: Inventory, deg: int) -> List[Cand]:
    """Every valid base at this degree (neutrality and span hold). Small enough to enumerate (about 2,000 at degree 2).
    One Cand per (order, composition, neutral fingering). The transposability test runs once per (order, composition),
    since it does not depend on the fingering. Degree 1 gives about 9,000 candidates, so enumeration takes a
    noticeable part of the time budget there."""
    out = []
    comps = vs.misaligned_compositions(deg)
    for t in inv.tuples:
        pitches = [p for c in t for p in c]
        for comp in comps:
            tr = None
            for a in valid_assignments(t, comp, inv.opts):
                if tr is None:
                    tr = bool(config.TRANSPOSITION_KEY) and has_transposition(pitches, comp, config.KEY,
                                                                              config.TRANSPOSITION_KEY)
                out.append(Cand(t, comp, a, tr))
    return out


def _compatible(c: Cand, F: Dict[Tuple[int, ...], int]) -> bool:
    """True if the candidate fingers every chunk the set already has (F) the same way (a chunk not in F is free)."""
    return all(F.get(ch_, j) == j for ch_, j in c.fing().items())


def sample_solution(inv: Inventory, cands: Sequence[Cand], deg: int, k: int, n_trained: int,
                    rng: random.Random) -> Optional[Solution]:
    """Build a set of k bases from compatible candidates (same fingering for a shared chunk), preferring
    candidates that reuse chunks already in the set, within n_trained chunks.

    Weights: (1 + 4 * shared^2) * (1 + 3 * transposable), shared = chunks the candidate shares with the set so far.
    Reusing chunks is what makes every chunk occur in >= 2 bases; preferring transposable bases gives played
    transpositions. The first base is transposable 70 % of the time (if any exists). None if the set cannot be
    completed or fails feasible()."""
    tr = [c for c in cands if c.transposable]
    first = rng.choice(tr) if tr and rng.random() < 0.7 else rng.choice(cands)
    chosen = [first]
    F = dict(first.fing())
    P = set(first.order)
    while len(chosen) < k:
        # compatible candidates: new order, same fingering for known chunks, chunk count stays within n_trained
        orders = {c.order for c in chosen}
        pool = [c for c in cands if c.order not in orders and _compatible(c, F) and len(P | set(c.order)) <= n_trained]
        if not pool:
            return None
        w = [(1 + 4 * len(P & set(c.order)) ** 2) * (1 + 3 * c.transposable) for c in pool]
        nxt = rng.choices(pool, weights=w)[0]
        chosen.append(nxt)
        F.update(nxt.fing())
        P |= set(nxt.order)
    sol = Solution(deg, sorted(P), F, [(c.order, c.comp) for c in chosen])
    return sol if feasible(inv, sol) else None


def neighbours(inv: Inventory, cands: Sequence[Cand], sol: Solution, rng: random.Random,
               n_trained: int, n: int = 6) -> List[Solution]:
    """Replace one base by another valid base that fits the others (same fingering for shared chunks).
    Returns up to n distinct feasible neighbours. The fingering map F is rebuilt from the kept bases only, so a chunk
    used only by the removed base becomes free again."""
    out: List[Solution] = []
    tries = 0
    while len(out) < n and tries < n * 8:
        tries += 1
        i = rng.randrange(len(sol.bases))
        keep = [b for j, b in enumerate(sol.bases) if j != i]
        F: Dict[Tuple[int, ...], int] = {}
        for t, comp in keep:
            for c, j in zip(t, next(valid_assignments(t, comp, inv.opts, fixed=sol.fingering))):
                F[c] = j
        P = {c for t, _ in keep for c in t}
        orders = {t for t, _ in keep}
        pool = [c for c in cands if c.order not in orders and _compatible(c, F) and len(P | set(c.order)) <= n_trained]
        if not pool:
            continue
        w = [(1 + 4 * len(P & set(c.order)) ** 2) * (1 + 3 * c.transposable) for c in pool]
        nxt = rng.choices(pool, weights=w)[0]
        F.update(nxt.fing())
        cand = Solution(sol.degree, sorted(P | set(nxt.order)), F, keep + [(nxt.order, nxt.comp)])
        if cand.key() != sol.key() and feasible(inv, cand):
            out.append(cand)
    return out


def search(inv: Inventory, deg: int, k: int, n_trained: Optional[int] = None, budget_s: Optional[float] = None,
           seed: int = 0, top: int = 3, log: Optional[Callable[[str], None]] = None) -> Tuple[List[Evaluated], Dict]:
    """Random sampling (about 60% of the time) followed by local moves from the best sets.
    Returns (all evaluated sets ranked by score, statistics). The clock starts before candidate enumeration, so the
    enumeration time counts against the budget. Every distinct set is evaluated once (`seen`, keyed by Solution.key)."""
    n_trained = config.N_TRAINED_CHUNKS if n_trained is None else n_trained
    budget = config.SEARCH_BUDGET_S if budget_s is None else budget_s
    rng = random.Random(config.SEED + 5000 + 97 * deg + 13 * k + seed)
    t0 = time.time()
    cands = candidates(inv, deg)
    seen: Dict[tuple, Evaluated] = {}
    stats = dict(candidates=len(cands), samples=0, feasible=0, evaluated=0, improved=0)

    def add(sol: Solution) -> Optional[Evaluated]:
        if sol.key() in seen:
            return None
        ev = evaluate(inv, sol, seed=len(seen))
        seen[sol.key()] = ev
        stats["evaluated"] += 1
        return ev

    # phase 1: random feasible sets
    while time.time() - t0 < 0.6 * budget:
        stats["samples"] += 1
        sol = sample_solution(inv, cands, deg, k, n_trained, rng)
        if sol is None:
            continue
        stats["feasible"] += 1
        add(sol)
    best = lambda: sorted(seen.values(), key=lambda e: e.score)
    # phase 2: local search; pick one of the `top` best sets and try a few neighbours
    while time.time() - t0 < budget and seen:
        parent = rng.choice(best()[:top])
        for cand in neighbours(inv, cands, parent.solution, rng, n_trained, n=4):
            ev = add(cand)
            if ev and ev.score < parent.score:
                stats["improved"] += 1
        if time.time() - t0 >= budget:
            break
    ranked = best()
    stats["best_score"] = ranked[0].score if ranked else None
    stats["best_objective"] = ranked[0].objective if ranked else None
    stats["best_E1"] = round(ranked[0].e1, 3) if ranked else None
    stats["best_E2"] = round(ranked[0].e2, 3) if ranked else None
    stats["lowest_E1_any_set"] = round(min(e.e1 for e in ranked), 3) if ranked else None
    if log:
        log(f"degree {deg}, {k} bases: {stats}")
    return ranked, stats
