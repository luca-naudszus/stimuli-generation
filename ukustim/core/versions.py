"""
versions.py
=============================
Chunking versions (aligned / misaligned motor chunks), the physical neutrality rule, motor chunk IDs.
Build spec section 4.

This module knows nothing about pitches; it deals with WHERE boundaries lie in a 12-note item.

Indexing (used throughout the pipeline):
- notes are 0-based (Python lists), transitions are 1-based: transition t lies between note t-1 and note t
  (0-based), i.e. between the t-th and (t+1)-th note when counting from 1;
- M = musical boundaries = {3, 6, 9} (after each 3-note chunk);
- a COMPOSITION is a tuple of motor-chunk lengths (2s and 3s summing to 12), e.g. (3, 2, 3, 2, 2); it describes the
  misaligned motor chunking of an item. The aligned chunking is always (3, 3, 3, 3);
- B = boundaries(composition) = running sums, e.g. (3, 2, 3, 2, 2) -> {3, 5, 8, 10};
- a motor chunk is a 0-based note range [start, end) (segments()); a transition t lies inside it iff start < t < end.

Flow of use:
  compositions() -> misaligned_compositions(degree)                 which motor chunkings exist
  forbidden_crossings(comp) = M delta B                             used by the fingering search and the checks
  neutrality_violations(positions, comp)                            string changes in M delta B (empty = neutral)
  motor_chunks(positions, comp, mode) = segments + motor_id         cut an item into named motor chunks
  crossing_motor_ids(positions, comp)                               the ones that span a musical boundary
"""

from typing import FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core.fretboard import Pos


def musical_boundaries() -> FrozenSet[int]:
    """M: the transitions after each musical chunk, {3, 6, 9} for 4 chunks of 3 notes."""
    return frozenset(config.CHUNK_LEN * i for i in range(1, config.N_CHUNKS))


def compositions(total: Optional[int] = None, parts: Sequence[int] = None) -> List[Tuple[int, ...]]:
    """All ordered compositions of `total` notes into motor chunks of the allowed lengths.
    12 notes into 2s and 3s gives 12 compositions (from 2-2-2-2-2-2 to 3-3-3-3). Recursive search: append a part
    that still fits, recurse on the rest, pop (backtracking)."""
    total = config.N_NOTES if total is None else total
    parts = config.MOTOR_PARTS if parts is None else parts
    out: List[Tuple[int, ...]] = []

    def rec(rest, acc):
        if rest == 0:                 # the parts sum exactly to total
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
    """The aligned motor chunking: motor chunks = musical chunks, (3, 3, 3, 3)."""
    return (config.CHUNK_LEN,) * config.N_CHUNKS


def boundaries(comp: Sequence[int]) -> FrozenSet[int]:
    """B: transitions after each motor chunk = running sums of the composition without the final total.
    (3, 2, 3, 2, 2) -> {3, 5, 8, 10}."""
    out, c = [], 0
    for p in comp[:-1]:
        c += p
        out.append(c)
    return frozenset(out)


def degree(comp: Sequence[int]) -> int:
    """Number of musical boundaries that are not motor boundaries: |M - B|. (3, 2, 3, 2, 2): {6, 9} -> 2."""
    return len(musical_boundaries() - boundaries(comp))


def misaligned_compositions(deg: Optional[int] = None) -> List[Tuple[int, ...]]:
    """Compositions that differ from the aligned one and have the given degree of misalignment
    (3 at degree 1, 5 at degree 2, 3 at degree 3). Every loop over 'possible chunkings' in the pipeline uses this."""
    deg = config.MISALIGNMENT_DEGREE if deg is None else deg
    return [c for c in compositions() if boundaries(c) != musical_boundaries() and degree(c) == deg]


def comp_to_str(comp: Sequence[int]) -> str:
    """(3, 2, 3, 2, 2) -> '3-2-3-2-2' (CSV files, tables, reports)."""
    return "-".join(str(c) for c in comp)


def comp_from_str(s: str) -> Tuple[int, ...]:
    """'3-2-3-2-2' or '3+2+3+2+2' -> (3, 2, 3, 2, 2)."""
    return tuple(int(x) for x in s.replace("+", "-").split("-"))


def forbidden_crossings(comp: Sequence[int]) -> FrozenSet[int]:
    """M delta B: transitions where a string change would favour one chunking.

    A string change is a physical seam in the movement, i.e. a natural place for a boundary. Both chunking versions
    use the same notes and fingering, so the physical layout must favour neither:
      - in M and B (a boundary in both chunkings): allowed;
      - in neither (inside a chunk in both): allowed;
      - in M only or in B only: forbidden, since it would hand that chunking a physical boundary.
    The last two together are the symmetric difference M ^ B. (3, 2, 3, 2, 2) -> {5, 6, 8, 9, 10}."""
    return musical_boundaries() ^ boundaries(comp)


def string_crossings(positions: Sequence[Pos]) -> Set[int]:
    """Transitions (1-based) with a string change. Transition t compares note t-1 and note t (0-based)."""
    return {t for t in range(1, len(positions)) if positions[t - 1].string != positions[t].string}


def neutrality_violations(positions: Sequence[Pos], comp: Sequence[int]) -> Set[int]:
    """String changes that fall in M delta B (build spec section 4). Empty set = the fingering is neutral.
    Needs a complete item; the fingering search applies the same test chunk by chunk instead (core/fingering.py)."""
    return string_crossings(positions) & forbidden_crossings(comp)


def segments(comp: Sequence[int]) -> List[Tuple[int, int]]:
    """0-based [start, end) ranges of the motor chunks. (3, 2, 3, 2, 2) -> [(0,3), (3,5), (5,8), (8,10), (10,12)].
    positions[start:end] is one motor chunk. Also used by the accent probe (start notes are loud) and the motor-only
    recombination (cuts bases into motor-chunk pieces)."""
    out, c = [], 0
    for p in comp:
        out.append((c, c + p))
        c += p
    return out


def is_crossing(start: int, end: int) -> bool:
    """True if the 0-based range [start, end) spans a musical boundary.
    The chunk's internal transitions are start+1 .. end-1, so boundary t lies inside iff start < t < end.
    (5, 8) contains boundary 6 -> crossing; (3, 5) contains only transition 4 -> not crossing."""
    return any(start < t < end for t in musical_boundaries())


def motor_id(positions: Sequence[Pos], mode: str = "full") -> str:
    """Identity of a motor chunk. mode 'full' = string, fret and finger of its notes. mode 'lh' (left hand) =
    fret, finger and relative string pattern, so a string-pair shift shares its motor chunks with its base (Q7, Q8).

    Two motor chunks are 'the same' iff their IDs are equal strings. Examples for E1 E0 E1:
      full: 'E1/1-E0/0-E1/1'
      lh:   '1/1-0/0-1/1@+0,+0'   (fret/finger per note, '@', then the string change after each note)
    Side effect of 'lh': C0-C2-C4 and G0-G2-G4 get the same ID (same hand movement on another string).
    Only called through motor_chunks()."""
    if mode == "full":
        return "-".join(p.label() for p in positions)
    if mode == "lh":
        return ("-".join(f"{p.fret}/{p.finger}" for p in positions) + "@"
                + ",".join(f"{d:+d}" for d in fb.relative_string_pattern(positions)))
    raise ValueError(f"unknown motor chunk mode {mode!r}")


def motor_chunks(positions: Sequence[Pos], comp: Sequence[int], mode: str = "full") -> List[Tuple[int, int, str]]:
    """Cut a fingered item into motor chunks: [(start, end, motor_id), ...] for the given composition.
    Pass aligned_composition() for the aligned version, item.composition for the misaligned one.
    Used by the trained proportions, recurrence (search and check 4), motor-chunk models, note table, variety report."""
    return [(a, b, motor_id(positions[a:b], mode)) for a, b in segments(comp)]


def crossing_motor_ids(positions: Sequence[Pos], comp: Sequence[int], mode: str = "full") -> Set[str]:
    """IDs of the motor chunks that span a musical boundary (these tie bases together: the minimum recurrence rule
    asks each base to share one of them with another base)."""
    return {mid for a, b, mid in motor_chunks(positions, comp, mode) if is_crossing(a, b)}
