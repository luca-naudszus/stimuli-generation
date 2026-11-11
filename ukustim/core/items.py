"""
items.py
=============================
Items (12-note sequences), chunk definitions (the inventory) and the generic item builder.
The family-member builders (alternate fingering, string-pair shift, played transposition, probes, recombined /
mixed / new-chunk items) live in ukustim/family/.  Build spec sections 5 and 6.

Two central data structures:
- ChunkDef / Registry: how each chunk of a set is played. The registry is the single source of truth for fingering;
  items are built from chunk IDs through it, so a chunk cannot be fingered two ways in one set.
- Item: one stimulus (12 notes) with everything the checks, models and exports need.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import versions as vs
from ukustim.core.fretboard import Pos


# ---------------------------------------------------------------------------
# Chunk definitions (the inventory)
# ---------------------------------------------------------------------------

@dataclass
class ChunkDef:
    """A musical chunk with its fingering. `alt` = the (single) alternate fingering, if any.
    role: trained | new | transposed (a trained chunk moved to another key, with its own fingering).

    Chunk IDs: trained chunks use the plain pitch ID ('C4-D4-E4'); chunks outside the trained inventory are
    'new:<pitches>' (with '~2', '~3' ... if the same pitches occur with another fingering); transposed chunks are
    'new:<key>:<pitches>'."""
    chunk_id: str
    pitches: Tuple[int, ...]
    fingering: Tuple[Pos, ...]
    alt: Optional[Tuple[Pos, ...]] = None
    role: str = "trained"

    def moved_notes(self) -> int:
        """How many notes the alternate fingering plays elsewhere than the main fingering (0 if no alternate)."""
        return 0 if self.alt is None else sum(a != b for a, b in zip(self.fingering, self.alt))


# chunk ID -> ChunkDef. Written by selection/assemble.py (trained chunks + alternates), family/generalization.py
# (new chunks) and family/transposition.py (transposed chunks); saved as chunks.csv by formats/loader.py.
Registry = Dict[str, ChunkDef]


def chunkdef_from_positions(positions: Sequence[Pos], alt: Optional[Sequence[Pos]] = None,
                            role: str = "trained", chunk_id: Optional[str] = None) -> ChunkDef:
    """ChunkDef from a fingering; pitches (and the default ID) follow from the positions."""
    pitches = tuple(fb.pitch_of(p.string, p.fret) for p in positions)
    return ChunkDef(chunk_id or ch.chunk_id(pitches), pitches, tuple(positions),
                    tuple(alt) if alt is not None else None, role)


def is_trained_id(chunk_id: str) -> bool:
    """Chunk IDs of chunks outside the trained inventory start with 'new:' (never practised, also transposed ones)."""
    return not chunk_id.startswith("new:")


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """One stimulus. Played items have 12 positions; listen-only probes have positions = None (pitches only).
    `composition` is the item's MISALIGNED motor chunking (the aligned one is always 3-3-3-3 and not stored).
    `key` is the key its scale degrees refer to (config.KEY, or the target key of a played transposition)."""
    item_id: str
    family_id: str
    layer: str                     # inventory | family | generalization | novel
    variant_type: str              # base | alternate fingering | string-pair shift | played transposition | probe:<type> |
                                   # recombined | mixed | new-chunk
    pitches: Tuple[int, ...]
    positions: Optional[Tuple[Pos, ...]]       # None = listen-only (no fingering)
    chunk_ids: Tuple[str, ...]                 # inventory ID, or 'new:<pitches>' for chunks outside the inventory
    composition: Tuple[int, ...] = ()          # misaligned motor composition
    base_item_id: str = ""
    preserved: str = ""                        # recombined items: musical-only | motor-only | both (derived, see tables)
    velocities: Optional[Tuple[int, ...]] = None   # accent probe only: MIDI velocity per note
    meta: Dict[str, str] = field(default_factory=dict)   # free-form notes (e.g. shift direction, transposition shift)
    key: Optional[str] = field(default_factory=lambda: config.KEY)

    @property
    def played(self) -> bool:
        """False for listen-only probes (no fingering); most motor code skips those."""
        return self.positions is not None

    def chunk_pitches(self) -> List[Tuple[int, ...]]:
        """The pitches cut into the 4 musical chunks (3 notes each)."""
        n = config.CHUNK_LEN
        return [self.pitches[i * n:(i + 1) * n] for i in range(config.N_CHUNKS)]

    def chunk_positions(self) -> List[Tuple[Pos, ...]]:
        """The positions cut into the 4 musical chunks."""
        n = config.CHUNK_LEN
        return [self.positions[i * n:(i + 1) * n] for i in range(config.N_CHUNKS)]


def build_item(item_id: str, family_id: str, layer: str, variant_type: str,
               chunk_ids: Sequence[str], registry: Registry, composition: Sequence[int],
               use_alt: Sequence[bool] = None, base_item_id: str = "", preserved: str = "",
               key: Optional[str] = "default") -> Item:
    """Build an item from chunk IDs: look each ID up in the registry and concatenate its fingering, or its
    alternate fingering where use_alt[i] is True (and an alternate exists). Pitches follow from the positions.
    Used for bases, alternates and recombined items, i.e. everything made of registered chunks.
    key='default' keeps Item's default (config.KEY)."""
    use_alt = use_alt or [False] * len(chunk_ids)
    pos: List[Pos] = []
    for cid, alt in zip(chunk_ids, use_alt):
        d = registry[cid]
        pos.extend(d.alt if (alt and d.alt) else d.fingering)
    pitches = tuple(fb.pitch_of(p.string, p.fret) for p in pos)
    item = Item(item_id, family_id, layer, variant_type, pitches, tuple(pos), tuple(chunk_ids),
                tuple(composition), base_item_id, preserved)
    if key != "default":
        item.key = key
    return item


def item_from_positions(item_id: str, family_id: str, layer: str, variant_type: str,
                        positions: Sequence[Pos], composition: Sequence[int], base_item_id: str = "",
                        preserved: str = "", key: Optional[str] = "default", chunk_ids: Sequence[str] = None,
                        meta: Optional[Dict[str, str]] = None) -> Item:
    """Item from explicit positions; musical chunk IDs default to 'new:<pitches>'.
    Used where the positions are computed rather than looked up: string-pair shifts, played transpositions and the
    motor-only recombined item (which passes its own chunk IDs)."""
    pitches = tuple(fb.pitch_of(p.string, p.fret) for p in positions)
    n = config.CHUNK_LEN
    cids = tuple(chunk_ids) if chunk_ids else tuple(
        "new:" + ch.chunk_id(pitches[i * n:(i + 1) * n]) for i in range(config.N_CHUNKS))
    item = Item(item_id, family_id, layer, variant_type, pitches, tuple(positions), cids, tuple(composition),
                base_item_id, preserved, meta=dict(meta or {}))
    if key != "default":
        item.key = key
    return item


# ---------------------------------------------------------------------------
# Structure test used while building (the validators repeat it independently)
# ---------------------------------------------------------------------------

def structurally_ok(positions: Sequence[Pos], comp: Sequence[int]) -> bool:
    """Neutral (no string change in M delta B) and on at most MAX_STRING_SPAN adjacent strings.
    Used by the alternate-fingering builder to test candidate fingerings."""
    return (not vs.neutrality_violations(positions, comp)
            and fb.strings_adjacent_span(positions) <= config.MAX_STRING_SPAN)
