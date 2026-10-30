"""
versions.py
=============================
Chunking versions (aligned / misaligned motor chunks), the physical neutrality rule, motor chunk IDs.
Build spec section 4. Transition t (1-based) lies between notes t and t+1.
"""

from typing import FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

import config
import fretboard as fb
from fretboard import Pos


def musical_boundaries() -> FrozenSet[int]:
    return frozenset(config.CHUNK_LEN * i for i in range(1, config.N_CHUNKS))


def compositions(total: Optional[int] = None, parts: Sequence[int] = None) -> List[Tuple[int, ...]]:
    """All ordered compositions of `total` notes into motor chunks of the allowed lengths."""
    total = config.N_NOTES if total is None else total
    parts = config.MOTOR_PARTS if parts is None else parts
    out: List[Tuple[int, ...]] = []

    def rec(rest, acc):
        if rest == 0:
            out.append(tuple(acc))
            return
        for p in parts:
            if p <= rest:
                acc.append(p)
                rec(rest - p, acc)
                acc.pop()

    rec(total, [])
    return out


def aligned_composition() -> Tuple[int, ...]:
    return (config.CHUNK_LEN,) * config.N_CHUNKS


def boundaries(comp: Sequence[int]) -> FrozenSet[int]:
    out, c = [], 0
    for p in comp[:-1]:
        c += p
        out.append(c)
    return frozenset(out)


def degree(comp: Sequence[int]) -> int:
    """Number of musical boundaries that are not motor boundaries."""
    return len(musical_boundaries() - boundaries(comp))


def misaligned_compositions(deg: Optional[int] = None) -> List[Tuple[int, ...]]:
    deg = config.MISALIGNMENT_DEGREE if deg is None else deg
    return [c for c in compositions() if boundaries(c) != musical_boundaries() and degree(c) == deg]


def comp_to_str(comp: Sequence[int]) -> str:
    return "-".join(str(c) for c in comp)


def comp_from_str(s: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in s.replace("+", "-").split("-"))


def forbidden_crossings(comp: Sequence[int]) -> FrozenSet[int]:
    """M delta B: transitions where a string change would favour one chunking."""
    return musical_boundaries() ^ boundaries(comp)


def string_crossings(positions: Sequence[Pos]) -> Set[int]:
    """Transitions (1-based) with a string change."""
    return {t for t in range(1, len(positions)) if positions[t - 1].string != positions[t].string}


def neutrality_violations(positions: Sequence[Pos], comp: Sequence[int]) -> Set[int]:
    return string_crossings(positions) & forbidden_crossings(comp)


def segments(comp: Sequence[int]) -> List[Tuple[int, int]]:
    """0-based [start, end) ranges of the motor chunks."""
    out, c = [], 0
    for p in comp:
        out.append((c, c + p))
        c += p
    return out


def is_crossing(start: int, end: int) -> bool:
    """True if the 0-based range [start, end) spans a musical boundary."""
    return any(start < t < end for t in musical_boundaries())


def motor_id(positions: Sequence[Pos]) -> str:
    return "-".join(p.label() for p in positions)


def motor_chunks(positions: Sequence[Pos], comp: Sequence[int]) -> List[Tuple[int, int, str]]:
    return [(a, b, motor_id(positions[a:b])) for a, b in segments(comp)]


def crossing_motor_ids(positions: Sequence[Pos], comp: Sequence[int]) -> Set[str]:
    return {mid for a, b, mid in motor_chunks(positions, comp) if is_crossing(a, b)}
