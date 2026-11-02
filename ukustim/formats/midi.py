"""
midi.py
=============================
Standard MIDI File (format 0) at config.BPM, written without external libraries. The item file has the notes
(time signature 3/4, one chunk per bar). With config.EXPORT_CLICK_TRACK a second file <item>_click.mid holds
a metronome with an accent on beat 1 (GM percussion, channel 10), for the pacing cue.
"""

from typing import List, Tuple

from ukustim import config
from ukustim.core.items import Item


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _wrap(track: bytearray) -> bytes:
    ppq = config.MIDI_PPQ
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big") + ppq.to_bytes(2, "big")
    return header + b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)


def _track(name: str, program_msg: bytes, events: List[Tuple[int, int, bytes]]) -> bytearray:
    ppq = config.MIDI_PPQ
    track = bytearray()
    track += _vlq(0) + b"\xff\x03" + _vlq(len(name)) + name.encode()
    track += _vlq(0) + b"\xff\x51\x03" + round(60_000_000 / config.BPM).to_bytes(3, "big")
    track += _vlq(0) + b"\xff\x58\x04" + bytes([config.BEATS_PER_BAR, 2, 24, 8])      # n/4
    if program_msg:
        track += _vlq(0) + program_msg
    events = sorted(events, key=lambda e: (e[0], e[1]))
    t = 0
    for tick, _, msg in events:
        track += _vlq(tick - t) + msg
        t = tick
    track += _vlq(max(config.N_NOTES * ppq - t, 0)) + b"\xff\x2f\x00"
    return track


def build_midi(item: Item) -> bytes:
    ppq = config.MIDI_PPQ
    gate = int(round(ppq * config.NOTE_GATE))
    events = []
    for i, pitch in enumerate(item.pitches):
        vel = item.velocities[i] if item.velocities else config.MIDI_VELOCITY
        events.append((i * ppq, 1, bytes([0x90, pitch, vel])))
        events.append((i * ppq + gate, 0, bytes([0x80, pitch, 0])))
    return _wrap(_track(item.item_id, bytes([0xC0, config.MIDI_PROGRAM]), events))


def build_click_midi(item: Item) -> bytes:
    """Metronome for the item: accent on beat 1 of every bar, soft clicks on the other beats."""
    ppq = config.MIDI_PPQ
    events = []
    for i in range(config.N_NOTES):
        vel = config.CLICK_VEL_ACCENT if i % config.BEATS_PER_BAR == 0 else config.CLICK_VEL_SOFT
        events.append((i * ppq, 1, bytes([0x99, config.CLICK_NOTE, vel])))
        events.append((i * ppq + ppq // 8, 0, bytes([0x89, config.CLICK_NOTE, 0])))
    return _wrap(_track(item.item_id + " click", b"", events))
