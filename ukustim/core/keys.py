"""
keys.py
=============================
Keys, scale degrees and transposition offsets (build spec sections 5 and 7).
"""

from typing import List, Optional, Sequence

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core.music_theory import ALL_KEY_ROOTS

# semitones above the tonic -> scale-degree label (major scale: 1..7; chromatic notes with b / #)
DEGREE_LABEL = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "#4", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}


def scale_degree(pitch: int, key: Optional[str]) -> str:
    """Scale degree of a MIDI pitch relative to a major key ('' for free chromatic / no key)."""
    if key is None:
        return ""
    return DEGREE_LABEL[(pitch - ALL_KEY_ROOTS[key]) % 12]


def interval_pattern(pitches: Sequence[int]) -> str:
    """Abstract (transposition-invariant) identity of a pitch sequence, e.g. '+2+2' for C-D-E."""
    return "".join(f"{b - a:+d}" for a, b in zip(pitches, pitches[1:]))


def transposition_offsets(pitches: Sequence[int], key_from: str, key_to: str) -> List[int]:
    """Semitone shifts that take key_from to key_to (a multiple-of-octave family) and keep every pitch
    playable in first position, smallest |shift| first."""
    base = (ALL_KEY_ROOTS[key_to] - ALL_KEY_ROOTS[key_from]) % 12
    out = []
    for s in range(base - 24, base + 25, 12):
        if s == 0:
            continue
        moved = [p + s for p in pitches]
        if all(fb.positions_for_pitch(p) for p in moved):
            out.append(s)
    return sorted(out, key=lambda s: (abs(s), s))
