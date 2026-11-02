"""
reference.py
=============================
Reference sample of valid bases for the difficulty z-scores (analysis/difficulty.py).
"""

import random
from typing import List, Optional

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import versions as vs
from ukustim.core.fingering import positions_of, valid_assignments
from ukustim.core.inventory import Inventory
from ukustim.core.items import Item


def reference_items(inv: Inventory, n: int = 3000, deg: Optional[int] = None, seed: int = 0) -> List[Item]:
    """Random valid bases (any order, composition of the given degree, random neutral fingering)."""
    rng = random.Random(config.SEED + 1000 + seed)
    deg = config.MISALIGNMENT_DEGREE if deg is None else deg
    comps = vs.misaligned_compositions(deg)
    out: List[Item] = []
    tuples = inv.tuples
    while len(out) < n:
        t = rng.choice(tuples)
        comp = rng.choice(comps)
        a = list(valid_assignments(t, comp, inv.opts))
        if not a:
            continue
        pos = positions_of(t, rng.choice(a), inv.opts)
        pitches = tuple(fb.pitch_of(p.string, p.fret) for p in pos)
        out.append(Item(f"ref{len(out)}", "ref", "reference", "base", pitches, pos,
                        tuple(ch.chunk_id(c) for c in t), comp))
    return out
