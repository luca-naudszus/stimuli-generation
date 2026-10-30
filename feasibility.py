"""
feasibility.py
=============================
Enumeration and search on the full constraint space (build spec sections 3-5, 8).

Tier 1  count_report(): chunks, junctions, chunk orders, and valid bases (order x misaligned composition x
        fingering) per degree of misalignment.
Tier 2  find_sets(): randomized search for complete prototype sets (>= N_BASES bases, N_TRAINED_CHUNKS
        chunks, recurrence satisfied) at a given degree; returns solutions and the success rate.
Then    assemble_family(): turns a solution into the full item list (alternates, shifts, probes,
        recombined, mixed, new-chunk items).
"""

import itertools
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import config
import chunks as ch
import fretboard as fb
import versions as vs
import items as it
from items import ChunkDef, Item, Registry

Chunk = Tuple[int, ...]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class Inventory:
    def __init__(self):
        self.chunks: List[Chunk] = ch.enumerate_chunks()
        self.graph = ch.junction_graph(self.chunks)
        self.opts = {c: ch.fingering_options(c) for c in self.chunks}
        self._tuples = None
        preds: Dict[Chunk, List[Chunk]] = {c: [] for c in self.chunks}
        for a, bs in self.graph.items():
            for b in bs:
                preds[b].append(a)
        self.preds = preds

    @property
    def tuples(self):
        if self._tuples is None:
            self._tuples = ch.enumerate_chunk_tuples(self.chunks, self.graph)
        return self._tuples


# ---------------------------------------------------------------------------
# Fingering assignments that satisfy neutrality and the string span
# ---------------------------------------------------------------------------

def valid_assignments(chunk_tuple: Sequence[Chunk], comp: Sequence[int], opts,
                      fixed: Optional[Dict[Chunk, int]] = None) -> Iterator[Tuple[int, ...]]:
    """Yield tuples of option indices (one per chunk) with no string crossing in M delta B and at most
    MAX_STRING_SPAN adjacent strings. `fixed` pins the option of some chunks."""
    F = vs.forbidden_crossings(comp)
    n = config.CHUNK_LEN
    k = len(chunk_tuple)

    def rec(i, chosen, prev_last, lo, hi):
        if i == k:
            yield tuple(chosen)
            return
        c = chunk_tuple[i]
        cand = range(len(opts[c])) if not fixed or c not in fixed else (fixed[c],)
        t0 = n * i
        for j in cand:
            o = opts[c][j]
            if any(x and (t0 + q + 1) in F for q, x in enumerate(o.crossings)):
                continue
            if i > 0 and prev_last != o.first and t0 in F:
                continue
            nlo, nhi = min(lo, min(o.strings)), max(hi, max(o.strings))
            if nhi - nlo + 1 > config.MAX_STRING_SPAN:
                continue
            chosen.append(j)
            yield from rec(i + 1, chosen, o.last, nlo, nhi)
            chosen.pop()

    yield from rec(0, [], -1, 99, -99)


def positions_of(chunk_tuple, assignment, opts) -> Tuple[fb.Pos, ...]:
    out = []
    for c, j in zip(chunk_tuple, assignment):
        out.extend(opts[c][j].positions)
    return tuple(out)


# ---------------------------------------------------------------------------
# Tier 1: counts
# ---------------------------------------------------------------------------

def count_report(inv: Optional[Inventory] = None, degrees=(1, 2, 3)) -> Dict:
    inv = inv or Inventory()
    rep = dict(n_chunks=len(inv.chunks),
               n_monotonic=sum(ch.is_monotonic(c) for c in inv.chunks),
               n_junction_pairs=sum(len(v) for v in inv.graph.values()),
               n_chunk_orders=len(inv.tuples),
               n_fingering_options=sum(len(v) for v in inv.opts.values()),
               n_chunks_with_alt=sum(len(v) > 1 for v in inv.opts.values()),
               degrees={})
    for d in degrees:
        comps = vs.misaligned_compositions(d)
        n_pairs = n_with = n_assign = 0
        orders_ok = set()
        for t in inv.tuples:
            for comp in comps:
                n_pairs += 1
                k = sum(1 for _ in valid_assignments(t, comp, inv.opts))
                if k:
                    n_with += 1
                    n_assign += k
                    orders_ok.add(t)
        used_chunks = {c for t in orders_ok for c in t}
        rep["degrees"][d] = dict(compositions=[vs.comp_to_str(c) for c in comps],
                                 order_x_composition=n_pairs, valid=n_with, fingering_assignments=n_assign,
                                 distinct_orders_valid=len(orders_ok), chunks_used=len(used_chunks))
    return rep


# ---------------------------------------------------------------------------
# Tier 2: prototype set search
# ---------------------------------------------------------------------------

@dataclass
class Solution:
    degree: int
    chunks: List[Chunk]
    fingering: Dict[Chunk, int]
    bases: List[Tuple[Tuple[Chunk, ...], Tuple[int, ...]]]     # (chunk order, misaligned composition)


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
# From a solution to the full family of items
# ---------------------------------------------------------------------------

def _choose_alternates(inv: Inventory, sol: Solution, rng: random.Random):
    """Pick one alternate fingering per chunk (or none) so that as many bases as possible get a valid
    alternate item. Returns (registry, alt_items_by_base)."""
    reg: Registry = {}
    movable = []
    for c in sol.chunks:
        base_opt = inv.opts[c][sol.fingering[c]]
        alts = [o for j, o in enumerate(inv.opts[c]) if j != sol.fingering[c]]
        reg[ch.chunk_id(c)] = ChunkDef(ch.chunk_id(c), c, base_opt.positions, None, "trained")
        if alts:
            movable.append((c, alts))
    best_score, best_reg = None, None
    ranges = [range(len(alts) + 1) for _, alts in movable]
    combos = list(itertools.product(*ranges))
    rng.shuffle(combos)
    for combo in combos[:400]:
        r2 = {k: ChunkDef(v.chunk_id, v.pitches, v.fingering, None, v.role) for k, v in reg.items()}
        for (c, alts), j in zip(movable, combo):
            if j > 0:
                r2[ch.chunk_id(c)].alt = alts[j - 1].positions
        n_ok, alt_items = 0, {}
        for bi, (t, comp) in enumerate(sol.bases):
            base = it.build_item(f"B{bi + 1}", f"F{bi + 1}", "family", "base", [ch.chunk_id(c) for c in t], r2, comp)
            a = it.alternate_item(base, r2)
            if a is not None:
                n_ok += 1
        moved_total = sum(v.moved_notes() for v in r2.values())
        score = (n_ok, -moved_total)
        if best_score is None or score > best_score:
            best_score, best_reg = score, r2
    return best_reg if best_reg is not None else reg


def _fresh_chunk_fingering(inv: Inventory, chunk_tuple: Sequence[Chunk], comp, rng: random.Random):
    a = list(valid_assignments(chunk_tuple, comp, inv.opts))
    return rng.choice(a) if a else None


def assemble_family(inv: Inventory, sol: Solution, seed: int = 0,
                    with_new_chunk_item: bool = True) -> Tuple[List[Item], Registry, List[str]]:
    """Full item list for a solution + notes about what could not be built."""
    rng = random.Random(config.SEED + seed)
    notes: List[str] = []
    reg = _choose_alternates(inv, sol, rng)
    items: List[Item] = []
    bases: List[Item] = []
    for bi, (t, comp) in enumerate(sol.bases):
        b = it.build_item(f"B{bi + 1}", f"F{bi + 1}", "family", "base", [ch.chunk_id(c) for c in t], reg, comp)
        bases.append(b)
        items.append(b)
    for b in bases:
        a = it.alternate_item(b, reg)
        if a:
            items.append(a)
        else:
            notes.append(f"{b.item_id}: no valid alternate fingering")
        s = it.string_pair_shift(b)
        if s:
            items.append(s)
        else:
            notes.append(f"{b.item_id}: string-pair shift impossible (strings do not fit)")
        items.extend(it.all_probes(b))
    comps = vs.misaligned_compositions(sol.degree)
    trained_motor = set()
    for b in bases:
        trained_motor |= {m for _, _, m in vs.motor_chunks(b.positions, b.composition)}
    base_orders = {tuple(b.chunk_ids) for b in bases}
    # recombined items: one that also preserves the misaligned motor chunks, one that preserves only the musical chunks
    found: Dict[str, Item] = {}
    cand = [t for t in itertools.permutations(sol.chunks, config.N_CHUNKS)
            if all(inv.graph[a].count(b) for a, b in zip(t, t[1:]))]
    rng.shuffle(cand)
    for t in cand:
        ids = tuple(ch.chunk_id(c) for c in t)
        if ids in base_orders:
            continue
        for comp in rng.sample(comps, len(comps)):
            a = next(valid_assignments(t, comp, inv.opts, fixed=sol.fingering), None)
            if a is None:
                continue
            pos = positions_of(t, a, inv.opts)
            motor = {m for _, _, m in vs.motor_chunks(pos, comp)}
            kind = "musical+motor" if motor <= trained_motor else "musical"
            if kind not in found:
                found[kind] = it.build_item(f"R{len(found) + 1}", "G", "generalization", "recombined",
                                            ids, reg, comp, preserved=kind)
            break
        if len(found) == 2:
            break
    for kind in ("musical+motor", "musical"):
        if kind in found:
            items.append(found[kind])
        else:
            notes.append(f"recombined item preserving {kind}: none found")
    # mixed item: 2 trained + 2 new chunks; new-chunk item: 4 new chunks
    outside = [c for c in inv.chunks if c not in set(sol.chunks)]

    def new_def(c, fing):
        cid = "new:" + ch.chunk_id(c)
        reg[cid] = ChunkDef(cid, c, fing, None, "new")
        return cid

    def build_generalization(item_id, vtype, trained_n):
        Pset = set(sol.chunks)
        cands = [t for t in inv.tuples if sum(c in Pset for c in t) == trained_n]
        rng.shuffle(cands)
        for t in cands[:20000]:
            trained = [c for c in t if c in Pset]
            comp = rng.choice(comps)
            a = next(valid_assignments(t, comp, inv.opts, fixed={c: sol.fingering[c] for c in trained}), None)
            if a is None:
                continue
            ids = []
            for c, j in zip(t, a):
                ids.append(ch.chunk_id(c) if c in Pset else new_def(c, inv.opts[c][j].positions))
            return it.build_item(item_id, "G", "generalization", vtype, ids, reg, comp)
        return None

    m = build_generalization("X1", "mixed", 2)
    if m:
        items.append(m)
    else:
        notes.append("mixed item: none found")
    if with_new_chunk_item:
        n = build_generalization("N1", "new-chunk", 0)
        if n:
            items.append(n)
        else:
            notes.append("new-chunk item: none found")
    return items, reg, notes


# ---------------------------------------------------------------------------
# Reference sample for the difficulty z-scores
# ---------------------------------------------------------------------------

def reference_items(inv: Inventory, n: int = 3000, deg: Optional[int] = None, seed: int = 0) -> List[Item]:
    """Random valid bases (any order, composition of the given degree, random neutral fingering)."""
    rng = random.Random(config.SEED + 1000 + seed)
    deg = config.MISALIGNMENT_DEGREE if deg is None else deg
    comps = vs.misaligned_compositions(deg)
    out: List[Item] = []
    tuples = inv.tuples
    while len(out) < n:
        t = rng.choice(tuples)
        comp = rng.choice(comps)
        a = list(valid_assignments(t, comp, inv.opts))
        if not a:
            continue
        pos = positions_of(t, rng.choice(a), inv.opts)
        pitches = tuple(fb.pitch_of(p.string, p.fret) for p in pos)
        out.append(Item(f"ref{len(out)}", "ref", "reference", "base", pitches, pos,
                        tuple(ch.chunk_id(c) for c in t), comp))
    return out


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
