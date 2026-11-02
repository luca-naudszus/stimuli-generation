"""
fretboard.py
=============================
Positions on the ukulele neck: (string, fret, left-hand finger), derived from the geometry.
"""

from typing import List, NamedTuple, Optional, Sequence

from ukustim import config
from ukustim.core.music_theory import NOTE_NAMES, midi_to_tone_name, major_scale_pcs
from ukustim.core.ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI, fretboard_euclidean_mm


class Pos(NamedTuple):
    string: str
    fret: int
    finger: int      # 0 = open string

    def label(self) -> str:
        return f"{self.string}{self.fret}/{self.finger}"


def finger_for(fret: int) -> int:
    if fret <= 0:
        return 0
    if config.FINGER_RULE == "fret":
        return min(fret, 4)
    raise ValueError(f"unknown FINGER_RULE {config.FINGER_RULE!r}")


def string_index(string: str) -> int:
    return STRING_ORDER.index(string)


def pitch_of(string: str, fret: int) -> int:
    return OPEN_STRING_MIDI[string] + fret


def make_pos(string: str, fret: int, finger: Optional[int] = None) -> Pos:
    return Pos(string, fret, finger_for(fret) if finger is None else finger)


def positions_for_pitch(midi: int, max_fret: Optional[int] = None) -> List[Pos]:
    """All playable positions, lowest fret first (ties: string order). First entry = 'Var. 1'."""
    max_fret = config.FRET_MAX if max_fret is None else max_fret
    out = [make_pos(s, midi - OPEN_STRING_MIDI[s]) for s in STRING_ORDER
           if 0 <= midi - OPEN_STRING_MIDI[s] <= max_fret]
    return sorted(out, key=lambda p: (p.fret, string_index(p.string)))


def key_pitch_classes():
    """Pitch classes of the key, or None for free chromatic."""
    return None if config.KEY is None else major_scale_pcs(config.KEY)


def available_pitches(max_fret: Optional[int] = None) -> List[int]:
    """Playable pitches in first position that belong to the key (all if KEY is None)."""
    max_fret = config.FRET_MAX if max_fret is None else max_fret
    pcs = key_pitch_classes()
    lo = min(OPEN_STRING_MIDI.values())
    hi = max(OPEN_STRING_MIDI.values()) + max_fret
    return [m for m in range(lo, hi + 1)
            if positions_for_pitch(m, max_fret) and (pcs is None or m % 12 in pcs)]


def pitch_name(midi: int) -> str:
    return midi_to_tone_name(midi)


def parse_position(token: str) -> Pos:
    """'C2' or 'C2/3' (string+fret, optional finger after '/')."""
    token = token.strip()
    finger = None
    if "/" in token:
        token, f = token.split("/")
        finger = int(f)
    string, fret = token[0].upper(), int(token[1:])
    if string not in STRING_ORDER:
        raise ValueError(f"unknown string in {token!r}")
    return make_pos(string, fret, finger)


def strings_adjacent_span(positions: Sequence[Pos]) -> int:
    """Number of adjacent strings needed to cover all positions (G-C-E-A order)."""
    idx = [string_index(p.string) for p in positions]
    return max(idx) - min(idx) + 1


def relative_string_pattern(positions: Sequence[Pos]) -> tuple:
    """String changes between consecutive notes (0 = same string, +1 = one string towards A, -1 towards G).
    Part of the movement identity (build spec Q8): a string-pair shift preserves it."""
    idx = [string_index(p.string) for p in positions]
    return tuple(b - a for a, b in zip(idx, idx[1:]))


def step_distance_mm(a: Pos, b: Pos) -> float:
    return fretboard_euclidean_mm((a.string, a.fret), (b.string, b.fret))
