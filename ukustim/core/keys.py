"""
keys.py
=============================
Keys, scale degrees and transposition offsets (build spec sections 5 and 7).

Used for:
- the scale_degree column of the note table and the scale-degree / nuisance models (relative to the item's key:
  config.KEY for most items, TRANSPOSITION_KEY for played transpositions);
- the abstract chunk ID (interval_pattern), which a transposed chunk shares with its original;
- finding the semitone shift of a played transposition (transposition_offsets).
"""

from typing import List, Optional, Sequence

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core.music_theory import ALL_KEY_ROOTS

# semitones above the tonic -> scale-degree label (major scale: 1..7; chromatic notes with b / #)
DEGREE_LABEL = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "#4", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}


def scale_degree(pitch: int, key: Optional[str]) -> str:
    """Scale degree of a MIDI pitch relative to a major key ('' for free chromatic / no key).
    E.g. E4 in C -> '3', F#4 in G -> '7', D#4 in C (mode-swap probe) -> 'b3'."""
    if key is None:
        return ""
    return DEGREE_LABEL[(pitch - ALL_KEY_ROOTS[key]) % 12]


def interval_pattern(pitches: Sequence[int]) -> str:
    """Abstract (transposition-invariant) identity of a pitch sequence, e.g. '+2+2' for C-D-E.
    Used as abstract_chunk_id: C-D-E and G-A-B (both '+2+2') share it, which is what the abstract-structure model
    needs."""
    return "".join(f"{b - a:+d}" for a, b in zip(pitches, pitches[1:]))


def transposition_offsets(pitches: Sequence[int], key_from: str, key_to: str) -> List[int]:
    """Semitone shifts that take key_from to key_to (a multiple-of-octave family) and keep every pitch
    playable in first position, smallest |shift| first.

    C -> G: the basic shift is +7 (mod 12), so the candidates are -17, -5, +7, +19 (and +31 is out of range).
    A shift survives only if every shifted pitch still has a position on frets 0..FRET_MAX (range C4..C#5).
    An empty list means the melody cannot be transposed to that key in first position (Q11)."""
    base = (ALL_KEY_ROOTS[key_to] - ALL_KEY_ROOTS[key_from]) % 12
    out = []
    for s in range(base - 24, base + 25, 12):      # the same key change in several octaves
        if s == 0:
            continue                               # same key: not a transposition
        moved = [p + s for p in pitches]
        if all(fb.positions_for_pitch(p) for p in moved):
            out.append(s)
    return sorted(out, key=lambda s: (abs(s), s))  # prefer the smallest move (closest register)
