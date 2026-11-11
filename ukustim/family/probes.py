"""
probes.py
=============================
Listen-only probes (build spec section 5; the types are parameters, decided later): audio only, no fingering.

Each probe is an Item with positions = None, so all motor code skips it; the auditory models and the A-IV reports
include it. Three types per base:
  mode swap      major -> minor (degrees 3, 6, 7 lowered); same contour, other intervals and scale degrees
  transposition  every pitch + PROBE_TRANSPOSITION_SEMITONES (default +2, C -> D); same intervals, other pitches
  accent         same notes, loudness accents on the first note of each MISALIGNED motor chunk: an auditory
                 regrouping of identical notes (A-III), only possible as listen-only
"""

from typing import List, Optional, Sequence

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import versions as vs
from ukustim.core.items import Item


def _probe(base: Item, kind: str, pitches: Sequence[int], velocities=None, key="default") -> Item:
    """Build a listen-only item from new pitches. Its musical chunks are 'new:<pitches>', except for the accent
    probe, whose notes (and so chunks) are the base's. key='default' = the base's key."""
    cids = tuple("new:" + ch.chunk_id(pitches[i * config.CHUNK_LEN:(i + 1) * config.CHUNK_LEN])
                 for i in range(config.N_CHUNKS))
    item = Item(f"{base.item_id}-p-{kind}", base.family_id, "family", f"probe:{kind}", tuple(pitches),
                None, cids if kind != "accent" else base.chunk_ids, base.composition, base.item_id,
                velocities=tuple(velocities) if velocities else None)
    item.key = base.key if key == "default" else key
    return item


def probe_transposition(base: Item, semitones: Optional[int] = None) -> Item:
    """The base melody shifted by `semitones` (default PROBE_TRANSPOSITION_SEMITONES). The probe's key is the base
    key shifted by the same amount, so its scale degrees equal the base's. Not limited to first position (listen-only)."""
    from ukustim.core.music_theory import ALL_KEY_ROOTS, NOTE_NAMES
    s = config.PROBE_TRANSPOSITION_SEMITONES if semitones is None else semitones
    key = None if base.key is None else NOTE_NAMES[(ALL_KEY_ROOTS[base.key] + s) % 12]
    return _probe(base, "transposition", [p + s for p in base.pitches], key=key)


def probe_mode_swap(base: Item) -> Item:
    """Major -> minor: lower scale degrees 3, 6, 7 by a semitone (relative to the key root).
    In C: E -> D#, A -> G#, B -> A# (printed with sharps). Contour stays; some intervals change."""
    if base.key is None:
        raise ValueError("mode swap needs a key")
    from ukustim.core.music_theory import ALL_KEY_ROOTS
    root = ALL_KEY_ROOTS[base.key]
    lowered = {(root + 4) % 12, (root + 9) % 12, (root + 11) % 12}      # pitch classes of degrees 3, 6, 7
    return _probe(base, "mode-swap", [p - 1 if p % 12 in lowered else p for p in base.pitches])


def probe_accent(base: Item) -> Item:
    """Same notes and isochronous timing; loudness accents regroup them: loud on the first note of each
    motor chunk of the base's misaligned composition (so the accent grouping crosses the musical chunks)."""
    comp = base.composition or vs.aligned_composition()
    loud = {a for a, _ in vs.segments(comp)}          # 0-based start note of each motor chunk
    vel = [config.ACCENT_LOUD if i in loud else config.ACCENT_SOFT for i in range(config.N_NOTES)]
    return _probe(base, "accent", base.pitches, vel)


def all_probes(base: Item) -> List[Item]:
    """The probes of one base, in report order (mode swap only if the base has a key)."""
    probes = [probe_transposition(base), probe_accent(base)]
    if base.key is not None:
        probes.insert(0, probe_mode_swap(base))
    return probes
