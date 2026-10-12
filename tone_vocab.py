"""
tone_vocab.py
=============================
Tone data, derived from the instrument geometry. Every tone label ('C5') has
one variation per playable (string, fret) position: 'C5 (Var. 1)', 'C5 (Var. 2)', ...
Var. 1 is the position with the lowest fret.
"""

from typing import Dict, List
import config
from ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI
from music_theory import midi_to_tone_name, variant_id
from melody_distance import pitch_to_positions


def build_tone_vocab(max_fret: int = config.MAX_FRET):
    lowest = min(OPEN_STRING_MIDI.values())
    highest = max(OPEN_STRING_MIDI.values()) + max_fret
    vocab: Dict[str, Dict] = {}
    variants: Dict[str, List[str]] = {}
    for midi in range(lowest, highest + 1):
        positions = sorted(pitch_to_positions(midi, max_fret),
                           key=lambda p: (p[1], STRING_ORDER.index(p[0])))
        if not positions:
            continue
        label = midi_to_tone_name(midi)
        ids = []
        for k, pos in enumerate(positions, start=1):
            vid = variant_id(label, k)
            vocab[vid] = dict(label=label, variant=k, midi=midi, position=pos)
            ids.append(vid)
        variants[label] = ids
    return vocab, variants


# variant ID -> data; label -> list of variant IDs
TONE_VOCAB, TONE_VARIANTS = build_tone_vocab()