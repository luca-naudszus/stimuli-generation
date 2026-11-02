"""
fingering.py
=============================
Search for fingerings of a chunk order that satisfy the physical rules: no string crossing in M delta B
(neutrality, build spec section 4) and at most MAX_STRING_SPAN adjacent strings (section 1).
Used by the set search, the family builders (played transposition, recombined items) and the reference sample.
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
    option of some chunks (a chunk is fingered identically wherever it recurs)."""
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
