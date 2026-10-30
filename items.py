"""
items.py
=============================
Items (12-note sequences) and family-member builders: base, alternate fingering,
string-pair shift, listen-only probes, recombined / mixed / new-chunk items.
Build spec sections 5 and 6.
"""

import itertools
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

import config
import chunks as ch
import fretboard as fb
import versions as vs
from fretboard import Pos
from ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI


# ---------------------------------------------------------------------------
# Chunk definitions (the inventory)
# ---------------------------------------------------------------------------

@dataclass
class ChunkDef:
    """A musical chunk with its fingering. `alt` = the (single) alternate fingering, if any."""
    chunk_id: str
    pitches: Tuple[int, ...]
    fingering: Tuple[Pos, ...]
    alt: Optional[Tuple[Pos, ...]] = None
    role: str = "trained"          # trained | new

    def moved_notes(self) -> int:
        return 0 if self.alt is None else sum(a != b for a, b in zip(self.fingering, self.alt))


Registry = Dict[str, ChunkDef]


def chunkdef_from_positions(positions: Sequence[Pos], alt: Optional[Sequence[Pos]] = None,
                            role: str = "trained", chunk_id: Optional[str] = None) -> ChunkDef:
    pitches = tuple(fb.pitch_of(p.string, p.fret) for p in positions)
    return ChunkDef(chunk_id or ch.chunk_id(pitches), pitches, tuple(positions),
                    tuple(alt) if alt is not None else None, role)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@dataclass
class Item:
    item_id: str
    family_id: str
    layer: str                     # inventory | family | generalization | novel
    variant_type: str              # base | alternate fingering | string-pair shift | probe:<type> | recombined | mixed | new-chunk
    pitches: Tuple[int, ...]
    positions: Optional[Tuple[Pos, ...]]       # None = listen-only (no fingering)
    chunk_ids: Tuple[str, ...]                 # inventory ID, or 'new:<pitches>' for chunks outside the inventory
    composition: Tuple[int, ...] = ()          # misaligned motor composition
    base_item_id: str = ""
    preserved: str = ""                        # recombined items: 'musical' or 'musical+motor'
    velocities: Optional[Tuple[int, ...]] = None
    meta: Dict[str, str] = field(default_factory=dict)

    @property
    def played(self) -> bool:
        return self.positions is not None

    def chunk_pitches(self) -> List[Tuple[int, ...]]:
        n = config.CHUNK_LEN
        return [self.pitches[i * n:(i + 1) * n] for i in range(config.N_CHUNKS)]

    def chunk_positions(self) -> List[Tuple[Pos, ...]]:
        n = config.CHUNK_LEN
        return [self.positions[i * n:(i + 1) * n] for i in range(config.N_CHUNKS)]


def build_item(item_id: str, family_id: str, layer: str, variant_type: str,
               chunk_ids: Sequence[str], registry: Registry, composition: Sequence[int],
               use_alt: Sequence[bool] = None, base_item_id: str = "", preserved: str = "") -> Item:
    use_alt = use_alt or [False] * len(chunk_ids)
    pos: List[Pos] = []
    for cid, alt in zip(chunk_ids, use_alt):
        d = registry[cid]
        pos.extend(d.alt if (alt and d.alt) else d.fingering)
    pitches = tuple(fb.pitch_of(p.string, p.fret) for p in pos)
    return Item(item_id, family_id, layer, variant_type, pitches, tuple(pos), tuple(chunk_ids),
                tuple(composition), base_item_id, preserved)


# ---------------------------------------------------------------------------
# Structure tests used while building (the validators repeat them independently)
# ---------------------------------------------------------------------------

def structurally_ok(positions: Sequence[Pos], comp: Sequence[int]) -> bool:
    return (not vs.neutrality_violations(positions, comp)
            and fb.strings_adjacent_span(positions) <= config.MAX_STRING_SPAN)


# ---------------------------------------------------------------------------
# Alternate fingering (per chunk; build spec section 5)
# ---------------------------------------------------------------------------

def alternate_item(base: Item, registry: Registry) -> Optional[Item]:
    """Alternate item of a base: the alternate fingering of each chunk that has one, using the largest
    subset of chunks that keeps neutrality and the string span; needs >= ALT_MIN_CHUNKS chunks and
    >= ALT_MIN_NOTES_MOVED moved notes. None if impossible."""
    with_alt = [i for i, cid in enumerate(base.chunk_ids)
                if cid in registry and registry[cid].alt is not None]
    for k in range(len(with_alt), config.ALT_MIN_CHUNKS - 1, -1):
        best = None
        for subset in itertools.combinations(with_alt, k):
            flags = [i in subset for i in range(len(base.chunk_ids))]
            cand = build_item(f"{base.item_id}-alt", base.family_id, "family", "alternate fingering",
                              base.chunk_ids, registry, base.composition, flags, base.item_id)
            moved = sum(a != b for a, b in zip(base.positions, cand.positions))
            if moved >= config.ALT_MIN_NOTES_MOVED and structurally_ok(cand.positions, cand.composition):
                if best is None or moved > best[0]:
                    best = (moved, cand)
        if best:
            return best[1]
    return None


# ---------------------------------------------------------------------------
# String-pair shift
# ---------------------------------------------------------------------------

def string_pair_shift(base: Item, direction: Optional[str] = None) -> Optional[Item]:
    """Move the whole strings-and-frets pattern one string set: 'down' (C-E-A -> G-C-E, strings move
    one place towards G) or 'up' (G-C-E -> C-E-A). direction=None tries 'down', then 'up'."""
    for d in ([direction] if direction else ["down", "up"]):
        delta = -1 if d == "down" else 1
        new = []
        ok = True
        for p in base.positions:
            j = fb.string_index(p.string) + delta
            if not 0 <= j < len(STRING_ORDER):
                ok = False
                break
            new.append(Pos(STRING_ORDER[j], p.fret, p.finger))
        if not ok:
            continue
        pitches = tuple(fb.pitch_of(p.string, p.fret) for p in new)
        cids = tuple("new:" + ch.chunk_id(pitches[i * config.CHUNK_LEN:(i + 1) * config.CHUNK_LEN])
                     for i in range(config.N_CHUNKS))
        return Item(f"{base.item_id}-shift", base.family_id, "family", "string-pair shift", pitches,
                    tuple(new), cids, base.composition, base.item_id, meta={"direction": d})
    return None


# ---------------------------------------------------------------------------
# Listen-only probes (types are parameters; build spec section 5)
# ---------------------------------------------------------------------------

def _probe(base: Item, kind: str, pitches: Sequence[int], velocities=None) -> Item:
    cids = tuple("new:" + ch.chunk_id(pitches[i * config.CHUNK_LEN:(i + 1) * config.CHUNK_LEN])
                 for i in range(config.N_CHUNKS))
    return Item(f"{base.item_id}-p-{kind}", base.family_id, "family", f"probe:{kind}", tuple(pitches),
                None, cids if kind != "accent" else base.chunk_ids, base.composition, base.item_id,
                velocities=tuple(velocities) if velocities else None)


def probe_transposition(base: Item, semitones: Optional[int] = None) -> Item:
    s = config.PROBE_TRANSPOSITION_SEMITONES if semitones is None else semitones
    return _probe(base, "transposition", [p + s for p in base.pitches])


def probe_mode_swap(base: Item) -> Item:
    """Major -> minor: lower scale degrees 3, 6, 7 by a semitone (relative to the key root)."""
    if config.KEY is None:
        raise ValueError("mode swap needs a key")
    from music_theory import ALL_KEY_ROOTS
    root = ALL_KEY_ROOTS[config.KEY]
    lowered = {(root + 4) % 12, (root + 9) % 12, (root + 11) % 12}
    return _probe(base, "mode-swap", [p - 1 if p % 12 in lowered else p for p in base.pitches])


def probe_accent(base: Item) -> Item:
    """Same notes and isochronous timing; loudness accents regroup them: loud on the first note of each
    motor chunk of the base's misaligned composition (so the accent grouping crosses the musical chunks)."""
    comp = base.composition or vs.aligned_composition()
    loud = {a for a, _ in vs.segments(comp)}
    vel = [config.ACCENT_LOUD if i in loud else config.ACCENT_SOFT for i in range(config.N_NOTES)]
    return _probe(base, "accent", base.pitches, vel)


def all_probes(base: Item) -> List[Item]:
    probes = [probe_transposition(base), probe_accent(base)]
    if config.KEY is not None:
        probes.insert(0, probe_mode_swap(base))
    return probes
