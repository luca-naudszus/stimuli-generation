"""
fingering.py
=============================
Neutral fingerings for a chunk order: which fingering option per chunk keeps every string crossing out of
M delta B and the whole item on at most MAX_STRING_SPAN adjacent strings (build spec sections 3 and 4).

A chunk order is a tuple of 4 chunks (pitch tuples). For each chunk there is a list of FingeringOptions
(chunks.fingering_options, stored per chunk in Inventory.opts). An ASSIGNMENT is a tuple of option indices, one per
chunk: (0, 0, 1, 3) = option 0 for chunk 1, option 0 for chunk 2, option 1 for chunk 3, option 3 for chunk 4.
"""

from typing import Dict, Iterator, Optional, Sequence, Tuple

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core import versions as vs

Chunk = Tuple[int, ...]


def valid_assignments(chunk_tuple: Sequence[Chunk], comp: Sequence[int], opts,
                      fixed: Optional[Dict[Chunk, int]] = None) -> Iterator[Tuple[int, ...]]:
    """Yield tuples of option indices (one per chunk) with no string crossing in M delta B and at most
    MAX_STRING_SPAN adjacent strings. `opts` maps a chunk to its list of FingeringOption; `fixed` pins the
    option of some chunks (a chunk is fingered identically wherever it recurs).

    Depth-first search, one chunk at a time, pruning as soon as a placed chunk breaks a rule. Because the item is
    incomplete during the search, the neutrality test is applied locally instead of calling
    vs.neutrality_violations:
      - a string change INSIDE chunk i at its internal transition q (0-based) is transition t0 + q + 1,
        where t0 = 3 * i is the transition just before the chunk;
      - a string change at the JUNCTION (previous chunk's last string != this chunk's first string) is transition t0.
    Both must avoid F = M delta B. The string span is tracked as the running min / max string index.

    `fixed`: {chunk: option index}. A pinned chunk has only that one candidate; it still has to pass the tests, so a
    pinned fingering can make the order impossible (nothing is yielded). With every chunk pinned the call is a
    yes / no check of one fingering. Callers: the set search (all chunks pinned to the set's fingering), recombined
    and mixed items (trained chunks pinned), played transpositions (already registered transposed chunks pinned).
    The index refers to the `opts` passed in, so callers with their own opts translate first.

    It is a generator: next(valid_assignments(...), None) asks "is there any?", list(...) gets all of them."""
    F = vs.forbidden_crossings(comp)
    n = config.CHUNK_LEN
    k = len(chunk_tuple)

    def rec(i, chosen, prev_last, lo, hi):
        # i = index of the chunk to place; chosen = option indices so far; prev_last = string of the previous note;
        # lo / hi = lowest and highest string index used so far
        if i == k:
            yield tuple(chosen)
            return
        c = chunk_tuple[i]
        cand = range(len(opts[c])) if not fixed or c not in fixed else (fixed[c],)
        t0 = n * i                           # transition just before chunk i (0 for the first chunk: none)
        for j in cand:
            o = opts[c][j]
            # string change inside the chunk at a forbidden transition?
            if any(x and (t0 + q + 1) in F for q, x in enumerate(o.crossings)):
                continue
            # string change at the junction with the previous chunk at a forbidden transition?
            if i > 0 and prev_last != o.first and t0 in F:
                continue
            # still within MAX_STRING_SPAN adjacent strings?
            nlo, nhi = min(lo, min(o.strings)), max(hi, max(o.strings))
            if nhi - nlo + 1 > config.MAX_STRING_SPAN:
                continue
            chosen.append(j)
            yield from rec(i + 1, chosen, o.last, nlo, nhi)
            chosen.pop()                     # backtrack

    yield from rec(0, [], -1, 99, -99)


def positions_of(chunk_tuple, assignment, opts) -> Tuple[fb.Pos, ...]:
    """The 12 positions of a chunk order under an assignment (option index per chunk)."""
    out = []
    for c, j in zip(chunk_tuple, assignment):
        out.extend(opts[c][j].positions)
    return tuple(out)
