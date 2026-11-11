"""
fretboard.py
=============================
Positions on the ukulele neck: (string, fret, left-hand finger), derived from the geometry.

A `Pos` is the basic motor unit of the pipeline. Everything about movement (motor chunks, neutrality, movement
identity, difficulty, tabs) is computed from sequences of Pos. Pitches follow from positions (pitch_of), never the
other way round, except when a pitch has to be placed on the neck (positions_for_pitch).

Build spec section 1: first position = frets 0-4; finger = fret number by default (index 1 ... little finger 4);
open string = finger 0.
"""

from typing import List, NamedTuple, Optional, Sequence

from ukustim import config
from ukustim.core.music_theory import NOTE_NAMES, midi_to_tone_name, major_scale_pcs
from ukustim.core.ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI, fretboard_euclidean_mm


class Pos(NamedTuple):
    """One note as played: string name, fret (0 = open), left-hand finger (0 = open string, 1-4)."""
    string: str
    fret: int
    finger: int      # 0 = open string

    def label(self) -> str:
        """Compact label used in IDs and CSVs: 'C2/2' = C string, fret 2, finger 2. Motor chunk IDs ('full' mode)
        are these labels joined with '-'."""
        return f"{self.string}{self.fret}/{self.finger}"


def finger_for(fret: int) -> int:
    """Default left-hand finger for a fret (config.FINGER_RULE). Only rule so far: 'fret' = finger equals fret
    (capped at 4). Consequence noted in the build spec (M-IV): finger and fret are then one feature."""
    if fret <= 0:
        return 0
    if config.FINGER_RULE == "fret":
        return min(fret, 4)
    raise ValueError(f"unknown FINGER_RULE {config.FINGER_RULE!r}")


def string_index(string: str) -> int:
    """0 = G, 1 = C, 2 = E, 3 = A (physical order across the neck)."""
    return STRING_ORDER.index(string)


def pitch_of(string: str, fret: int) -> int:
    """MIDI pitch of a string/fret: open-string pitch + one semitone per fret."""
    return OPEN_STRING_MIDI[string] + fret


def make_pos(string: str, fret: int, finger: Optional[int] = None) -> Pos:
    """Build a Pos; the finger defaults to finger_for(fret)."""
    return Pos(string, fret, finger_for(fret) if finger is None else finger)


def positions_for_pitch(midi: int, max_fret: Optional[int] = None) -> List[Pos]:
    """All places on the neck (frets 0..max_fret) where this pitch can be played, lowest fret first
    (ties: string order). First entry = 'Var. 1', the default fingering.
    In C major first position only E4, G4, A4 and B4 have two entries; that limits alternate fingerings."""
    max_fret = config.FRET_MAX if max_fret is None else max_fret
    # a string can play the pitch if the needed fret (pitch - open pitch) is within 0..max_fret
    out = [make_pos(s, midi - OPEN_STRING_MIDI[s]) for s in STRING_ORDER
           if 0 <= midi - OPEN_STRING_MIDI[s] <= max_fret]
    return sorted(out, key=lambda p: (p.fret, string_index(p.string)))


def key_pitch_classes():
    """Pitch classes of the key, or None for free chromatic."""
    return None if config.KEY is None else major_scale_pcs(config.KEY)


def available_pitches(max_fret: Optional[int] = None) -> List[int]:
    """Playable pitches in first position that belong to the key (all if KEY is None).
    C major, frets 0-4: C4 D4 E4 F4 G4 A4 B4 C5 (8 pitches); this is the alphabet chunks are built from."""
    max_fret = config.FRET_MAX if max_fret is None else max_fret
    pcs = key_pitch_classes()
    lo = min(OPEN_STRING_MIDI.values())                     # lowest open string (C4)
    hi = max(OPEN_STRING_MIDI.values()) + max_fret          # highest string at the top fret (A string, fret 4 = C#5)
    return [m for m in range(lo, hi + 1)
            if positions_for_pitch(m, max_fret) and (pcs is None or m % 12 in pcs)]


def pitch_name(midi: int) -> str:
    return midi_to_tone_name(midi)


def parse_position(token: str) -> Pos:
    """Parse a position token from a CSV: 'C2' or 'C2/3' (string + fret, optional finger after '/')."""
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
    """Number of adjacent strings needed to cover all positions (G-C-E-A order).
    E.g. a pattern on C and A spans 3 (C, E, A), even if E is not played. Limited by config.MAX_STRING_SPAN = 3
    so that a string-pair shift to the neighbouring strings is always possible."""
    idx = [string_index(p.string) for p in positions]
    return max(idx) - min(idx) + 1


def relative_string_pattern(positions: Sequence[Pos]) -> tuple:
    """String changes between consecutive notes (0 = same string, +1 = one string towards A, -1 towards G).
    Part of the movement identity (build spec Q8): a string-pair shift preserves it, because every note moves by the
    same string step. Example: C0 C2 E0 -> (0, +1)."""
    idx = [string_index(p.string) for p in positions]
    return tuple(b - a for a, b in zip(idx, idx[1:]))


def step_distance_mm(a: Pos, b: Pos) -> float:
    """Physical hand travel between two positions (used by the difficulty metric)."""
    return fretboard_euclidean_mm((a.string, a.fret), (b.string, b.fret))
