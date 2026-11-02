"""
alternate.py
=============================
Alternate fingering (per musical chunk; build spec section 5): same pitches, a different movement.
"""

import itertools
from typing import Optional

from ukustim import config
from ukustim.core.items import Item, Registry, build_item, structurally_ok


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
                              base.chunk_ids, registry, base.composition, flags, base.item_id, key=base.key)
            moved = sum(a != b for a, b in zip(base.positions, cand.positions))
            if moved >= config.ALT_MIN_NOTES_MOVED and structurally_ok(cand.positions, cand.composition):
                if best is None or moved > best[0]:
                    best = (moved, cand)
        if best:
            return best[1]
    return None
