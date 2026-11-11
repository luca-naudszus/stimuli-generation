"""
chunks.py
=============================
Musical chunks: enumeration, within-chunk rules, junction (boundary) cue, fingering options.
Build spec section 3.

A musical chunk is a tuple of CHUNK_LEN (= 3) MIDI pitches, e.g. (60, 62, 64) = C4-D4-E4. Chunks are identified by
their pitches (chunk_id gives the readable form 'C4-D4-E4'); fingering is a separate layer (fingering_options here,
the choice per set in core/fingering.py and the registry in core/items.py).

The order of work in this module:
  1. enumerate_chunks()        every pitch triple over the key's pitches that passes the within-chunk rules
                               (strict rule: 12 monotonic stepwise chunks in C major)
  2. junction_cues / junction_ok   is there a boundary cue between chunk A and chunk B?
  3. junction_graph()          chunk -> chunks that may follow it (80 edges under the strict rule)
  4. enumerate_chunk_tuples()  every path of N_CHUNKS (= 4) distinct chunks through that graph = every chunk order a
                               base could have (2,476)
  5. fingering_options()       every way to finger one chunk in first position (used by core/fingering.py)

The boundary cue is a property of the JUNCTION (last note of A, first note of B), not of a single chunk; that is why
it lives in a graph over chunk pairs.
"""

import itertools
from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core.fretboard import Pos


def intervals(pitches: Sequence[int]) -> List[int]:
    """Signed semitone steps between consecutive pitches: C4-D4-E4 -> [+2, +2]."""
    return [b - a for a, b in zip(pitches, pitches[1:])]


def sign(x: int) -> int:
    """-1, 0 or +1 (direction of an interval)."""
    return (x > 0) - (x < 0)


def chunk_id(pitches: Sequence[int]) -> str:
    """Readable ID of a musical chunk, e.g. 'C4-D4-E4'. Chunks outside the trained inventory get a 'new:' prefix
    elsewhere (family/generalization.register_new, family/transposition)."""
    return "-".join(fb.pitch_name(p) for p in pitches)


def is_monotonic(pitches: Sequence[int]) -> bool:
    """All intervals in the same direction (all up or all down). Needed by the direction cue."""
    iv = intervals(pitches)
    return all(sign(i) == sign(iv[0]) for i in iv)


def has_turning_point(pitches: Sequence[int]) -> bool:
    """True if the direction changes inside the chunk (X-Y-X shapes such as E-F-E)."""
    iv = [sign(i) for i in intervals(pitches) if i != 0]     # directions, ignoring repeats
    return any(a != b for a, b in zip(iv, iv[1:]))


def within_chunk_problems(pitches: Sequence[int]) -> List[str]:
    """Violations of the rules inside one chunk (no competing cues, no consecutive repeats, and, unless
    config.TURNING_POINT_CHUNKS = 'allow', no turning point). Empty list = valid chunk.

    Why these rules (build spec section 3): a boundary must be marked at the junction, so nothing inside a chunk may
    look like a boundary. A turning point or an interval >= LEAP_MIN inside a chunk would be a competing cue; a repeated
    note has no direction and groups on its own. The messages are reused by the validators (check 3)."""
    out = []
    if config.TURNING_POINT_CHUNKS == "forbid" and has_turning_point(pitches):
        out.append("turning point inside chunk (direction change) competes with the boundary cue")
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
    are monotonic inside.
    Returns the set of cues that hold ({} = no boundary cue, the pair may not be adjacent).

    Examples (b = boundary interval):
      C-D-E | D-E-F   b = -2: direction (A rises, boundary falls)
      C-D-E | G-A-B   b = +3: leap (3 > every within-chunk step of 2)
      E-D-C | G-A-B   b = +7: leap and direction
      C-D-E | E-F-G   b =  0: none (a repeated note is not a cue)"""
    b = pb[0] - pa[-1]                       # the boundary interval: last note of A -> first note of B
    if b == 0 or abs(b) > config.LEAP_MAX:   # repeated note, or a jump larger than the maximum leap
        return set()
    ia, ib = intervals(pa), intervals(pb)
    cues = set()
    # leap cue: big enough, and bigger than anything inside either chunk (else the inside would look like a boundary)
    if config.ALLOW_LEAP_CUE and abs(b) >= config.LEAP_MIN and abs(b) > max(abs(x) for x in ia + ib):
        cues.add("leap")
    # direction cue: the melody turns AT the junction; only meaningful if neither chunk turns inside
    if (config.ALLOW_DIRECTION_CUE and sign(b) != sign(ia[-1])
            and is_monotonic(pa) and is_monotonic(pb)):
        cues.add("direction")
    return cues


def junction_ok(pa: Sequence[int], pb: Sequence[int]) -> bool:
    """True if at least one boundary cue holds between A and B."""
    return bool(junction_cues(pa, pb))


@dataclass(frozen=True)
class FingeringOption:
    """One way to finger a chunk (3 positions) plus facts needed by the neutrality search (core/fingering.py):
    which strings it uses, its first and last string (for the junction with neighbouring chunks) and where it
    changes string internally."""
    positions: Tuple[Pos, ...]

    @property
    def strings(self) -> Tuple[int, ...]:
        """String index of each note (0 = G ... 3 = A)."""
        return tuple(fb.string_index(p.string) for p in self.positions)

    @property
    def first(self) -> int:
        """String of the first note (compared with the previous chunk's last string at the junction)."""
        return self.strings[0]

    @property
    def last(self) -> int:
        """String of the last note (compared with the next chunk's first string)."""
        return self.strings[-1]

    @property
    def crossings(self) -> Tuple[bool, ...]:
        """For each of the chunk's internal transitions: does the string change? (length CHUNK_LEN - 1)"""
        s = self.strings
        return tuple(a != b for a, b in zip(s, s[1:]))

    def label(self) -> str:
        return " ".join(p.label() for p in self.positions)


def fingering_options(pitches: Sequence[int]) -> List[FingeringOption]:
    """All fingerings of a chunk within the fret limit: the Cartesian product of each note's positions.
    Index 0 = lowest frets everywhere ('Var. 1'). E.g. E-F-G has 2 x 1 x 2 = 4 options
    (E4 on E0 or C4; F4 only on E1; G4 on G0 or E3)."""
    per_note = [fb.positions_for_pitch(p) for p in pitches]
    return [FingeringOption(tuple(c)) for c in itertools.product(*per_note)]


def enumerate_chunks() -> List[Tuple[int, ...]]:
    """All valid musical chunks over the key's pitches: try every pitch triple (8^3 = 512 in C major) and keep those
    without within-chunk problems (12 under the strict rule)."""
    pitches = fb.available_pitches()
    out = []
    for c in itertools.product(pitches, repeat=config.CHUNK_LEN):
        if not within_chunk_problems(c):
            out.append(c)
    return out


def junction_graph(chunks: Sequence[Tuple[int, ...]]) -> Dict[Tuple[int, ...], List[Tuple[int, ...]]]:
    """chunk -> chunks that may follow it directly (a boundary cue holds at the junction).
    A chunk never follows itself (b != a), whatever ALLOW_CHUNK_REPEAT_IN_ITEM says."""
    return {a: [b for b in chunks if b != a and junction_ok(a, b)] for a in chunks}


def enumerate_chunk_tuples(chunks=None, graph=None, n=None) -> List[Tuple[Tuple[int, ...], ...]]:
    """All ordered N_CHUNKS-tuples of chunks with a valid cue at every junction.

    Depth-first walk through the junction graph: start from every chunk, extend the current prefix only with
    successors of its LAST chunk (so every junction already has a cue), skip chunks already used (unless
    ALLOW_CHUNK_REPEAT_IN_ITEM), and record the prefix when it has n chunks. `prefix` is one shared list; append /
    pop around the recursive call is the backtracking step. Only musical rules are applied here; whether an order can
    be fingered neutrally is decided later (core/fingering.py)."""
    n = config.N_CHUNKS if n is None else n
    chunks = enumerate_chunks() if chunks is None else chunks
    graph = junction_graph(chunks) if graph is None else graph
    out = []

    def rec(prefix):
        if len(prefix) == n:                 # complete order
            out.append(tuple(prefix))
            return
        for nxt in graph[prefix[-1]]:        # only chunks that may follow the last one
            if not config.ALLOW_CHUNK_REPEAT_IN_ITEM and nxt in prefix:
                continue                     # a base uses distinct musical chunks
            prefix.append(nxt)
            rec(prefix)
            prefix.pop()                     # backtrack: try the next successor

    for c in chunks:                         # every chunk can open an item
        rec([c])
    return out
