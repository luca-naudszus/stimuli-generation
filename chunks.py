"""
chunks.py
=============================
Musical chunks: enumeration, within-chunk rules, junction (boundary) cue, fingering options.
Build spec section 3.
"""

import itertools
from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple

import config
import fretboard as fb
from fretboard import Pos


def intervals(pitches: Sequence[int]) -> List[int]:
    return [b - a for a, b in zip(pitches, pitches[1:])]


def sign(x: int) -> int:
    return (x > 0) - (x < 0)


def chunk_id(pitches: Sequence[int]) -> str:
    return "-".join(fb.pitch_name(p) for p in pitches)


def is_monotonic(pitches: Sequence[int]) -> bool:
    iv = intervals(pitches)
    return all(sign(i) == sign(iv[0]) for i in iv)


def within_chunk_problems(pitches: Sequence[int]) -> List[str]:
    """Violations of the rules inside one chunk (no competing cues, no consecutive repeats)."""
    out = []
    if len(pitches) != config.CHUNK_LEN:
        out.append(f"chunk has {len(pitches)} notes, expected {config.CHUNK_LEN}")
    for i in intervals(pitches):
        if i == 0:
            out.append("consecutive repeated note inside chunk")
        if abs(i) >= config.LEAP_MIN:
            out.append(f"within-chunk interval of {abs(i)} semitones (>= {config.LEAP_MIN}) competes with the boundary cue")
    return out


def junction_cues(pa: Sequence[int], pb: Sequence[int]) -> Set[str]:
    """Cues satisfied at the junction between chunk A (pitches pa) and chunk B (pb).
    'leap': LEAP_MIN <= |b| <= LEAP_MAX and |b| > every within-chunk interval of both chunks.
    'direction': boundary direction differs from the last within-chunk interval of A and both chunks
    are monotonic inside."""
    b = pb[0] - pa[-1]
    if b == 0 or abs(b) > config.LEAP_MAX:
        return set()
    ia, ib = intervals(pa), intervals(pb)
    cues = set()
    if config.ALLOW_LEAP_CUE and abs(b) >= config.LEAP_MIN and abs(b) > max(abs(x) for x in ia + ib):
        cues.add("leap")
    if (config.ALLOW_DIRECTION_CUE and sign(b) != sign(ia[-1])
            and is_monotonic(pa) and is_monotonic(pb)):
        cues.add("direction")
    return cues


def junction_ok(pa: Sequence[int], pb: Sequence[int]) -> bool:
    return bool(junction_cues(pa, pb))


@dataclass(frozen=True)
class FingeringOption:
    """One way to finger a chunk (3 positions) plus facts needed by the neutrality search."""
    positions: Tuple[Pos, ...]

    @property
    def strings(self) -> Tuple[int, ...]:
        return tuple(fb.string_index(p.string) for p in self.positions)

    @property
    def first(self) -> int:
        return self.strings[0]

    @property
    def last(self) -> int:
        return self.strings[-1]

    @property
    def crossings(self) -> Tuple[bool, ...]:
        s = self.strings
        return tuple(a != b for a, b in zip(s, s[1:]))

    def label(self) -> str:
        return " ".join(p.label() for p in self.positions)


def fingering_options(pitches: Sequence[int]) -> List[FingeringOption]:
    """All fingerings of a chunk within the fret limit. Index 0 = lowest frets everywhere ('Var. 1')."""
    per_note = [fb.positions_for_pitch(p) for p in pitches]
    return [FingeringOption(tuple(c)) for c in itertools.product(*per_note)]


def enumerate_chunks() -> List[Tuple[int, ...]]:
    """All valid musical chunks over the key's pitches."""
    pitches = fb.available_pitches()
    out = []
    for c in itertools.product(pitches, repeat=config.CHUNK_LEN):
        if not within_chunk_problems(c):
            out.append(c)
    return out


def junction_graph(chunks: Sequence[Tuple[int, ...]]) -> Dict[Tuple[int, ...], List[Tuple[int, ...]]]:
    """chunk -> chunks that may follow it directly."""
    return {a: [b for b in chunks if b != a and junction_ok(a, b)] for a in chunks}


def enumerate_chunk_tuples(chunks=None, graph=None, n=None) -> List[Tuple[Tuple[int, ...], ...]]:
    """All ordered N_CHUNKS-tuples of chunks with a valid cue at every junction."""
    n = config.N_CHUNKS if n is None else n
    chunks = enumerate_chunks() if chunks is None else chunks
    graph = junction_graph(chunks) if graph is None else graph
    out = []

    def rec(prefix):
        if len(prefix) == n:
            out.append(tuple(prefix))
            return
        for nxt in graph[prefix[-1]]:
            if not config.ALLOW_CHUNK_REPEAT_IN_ITEM and nxt in prefix:
                continue
            prefix.append(nxt)
            rec(prefix)
            prefix.pop()

    for c in chunks:
        rec([c])
    return out
