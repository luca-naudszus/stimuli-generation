"""Chunk rules, junction cue, keys, motor ids, metre."""

from tests.helpers import config, expect

from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import keys
from ukustim.core import versions as vs
from ukustim.core.fretboard import Pos
from ukustim.core.inventory import Inventory


def run():
    P = lambda *n: tuple(fb.available_pitches()[i] for i in n)   # indices into C4..C5
    # --- strict chunk rule (build spec v1.4): no turning point inside chunks -------------------------------
    config.TURNING_POINT_CHUNKS = "forbid"
    inv = Inventory()
    expect("strict rule: 12 chunks, all monotonic", len(inv.chunks) == 12 and all(ch.is_monotonic(c) for c in inv.chunks))
    expect("C-D-C (turning point) is invalid under the strict rule", bool(ch.within_chunk_problems((60, 62, 60))))
    config.TURNING_POINT_CHUNKS = "allow"
    inv2 = Inventory()
    expect("allow: 26 chunks (14 with a turning point)", len(inv2.chunks) == 26 and sum(ch.has_turning_point(c) for c in inv2.chunks) == 14)
    expect("C-D-C valid when turning points are allowed", not ch.within_chunk_problems((60, 62, 60)))
    config.TURNING_POINT_CHUNKS = "forbid"
    expect("consecutive repeat is invalid", bool(ch.within_chunk_problems((60, 60, 62))))
    expect("chunk with a 3-semitone interval is invalid", bool(ch.within_chunk_problems((60, 64, 65))))
    # --- junction cue ------------------------------------------------------------------------------------
    expect("leap cue (+3) accepted", ch.junction_cues(P(0, 1, 2), P(4, 5, 6)) == {"leap"})
    expect("direction cue accepted", ch.junction_cues((60, 62, 64), (62, 60, 59)) == {"direction"})
    expect("direction cue needs monotonic chunks", ch.junction_cues((60, 62, 64), (62, 64, 62)) == set())
    expect("no cue for a step in the same direction", ch.junction_cues(P(0, 1, 2), P(3, 4, 5)) == set())
    expect("repeated note across the boundary has no cue", ch.junction_cues(P(0, 1, 2), P(2, 3, 4)) == set())
    top = fb.available_pitches()[2]
    expect("leap above LEAP_MAX rejected", ch.junction_cues(P(0, 1, 2), (top + 8, top + 10, top + 12)) == set())
    expect("leap must exceed the larger within-chunk interval of both chunks", ch.junction_cues((60, 62, 64), (67, 69, 71)) == {"leap"}
           and ch.junction_cues((60, 62, 64), (67, 71, 72)) == set())
    # --- keys and transposition offsets ------------------------------------------------------------------
    expect("scale degrees in C", [keys.scale_degree(p, "C") for p in (60, 62, 64, 65, 67, 69, 71)] == list("1234567"))
    expect("chromatic degree labels", keys.scale_degree(66, "C") == "#4" and keys.scale_degree(63, "C") == "b3")
    expect("interval pattern is transposition invariant", keys.interval_pattern((60, 62, 64)) == keys.interval_pattern((67, 69, 71)) == "+2+2")
    expect("C->G: a melody within F4-C5 shifts down a fifth", keys.transposition_offsets((65, 67, 72), "C", "G") == [-5])
    expect("C->G: a melody within C4-F4 shifts up a fifth", keys.transposition_offsets((60, 62, 65), "C", "G") == [7])
    expect("C->G: a melody spanning C4-A4 cannot be transposed in first position", keys.transposition_offsets((60, 69), "C", "G") == [])
    # --- motor ids: 'lh' identity ignores the string, keeps fret / finger / relative string pattern -------
    a = (Pos("C", 0, 0), Pos("C", 2, 2), Pos("E", 0, 0))
    b = (Pos("G", 0, 0), Pos("G", 2, 2), Pos("C", 0, 0))      # same movement one string lower (a string-pair shift)
    c = (Pos("C", 0, 0), Pos("E", 2, 2), Pos("E", 0, 0))      # same frets and fingers, other string pattern
    expect("lh motor id: shifted chunk shares it", vs.motor_id(a, "lh") == vs.motor_id(b, "lh"))
    expect("full motor id: shifted chunk differs", vs.motor_id(a) != vs.motor_id(b))
    expect("lh motor id keeps the relative string pattern", vs.motor_id(a, "lh") != vs.motor_id(c, "lh"))
    # --- metre -------------------------------------------------------------------------------------------
    expect("3/4: one musical chunk per bar", config.BEATS_PER_BAR == config.CHUNK_LEN == 3)
