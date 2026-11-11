"""
solution.py
=============================
A candidate prototype set: chosen trained chunks with their fingering and the bases (chunk order +
misaligned composition).

A Solution is the compact form the search works with: no items yet, only
  - which musical chunks the set trains (chunks),
  - one fingering option per chunk (fingering: index into Inventory.opts[chunk]; the same everywhere in the set),
  - the bases as (chunk order, misaligned composition).
selection/assemble.assemble_family turns it into the full item list.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

Chunk = Tuple[int, ...]


@dataclass
class Solution:
    degree: int
    chunks: List[Chunk]
    fingering: Dict[Chunk, int]                                 # chunk -> index into its fingering options
    bases: List[Tuple[Tuple[Chunk, ...], Tuple[int, ...]]]     # (chunk order, misaligned composition)

    def key(self):
        """Hashable identity (order-independent), used to avoid evaluating the same set twice."""
        return (self.degree, tuple(sorted(self.bases)), tuple(sorted(self.fingering.items())))


def turning_cap_ok(chunks) -> bool:
    """Share of trained chunks with a turning point (X-Y-X) must stay within config.MAX_TURNING_SHARE
    (always true when turning-point chunks are forbidden, because none exist)."""
    from ukustim import config
    from ukustim.core import chunks as ch
    n = sum(ch.has_turning_point(c) for c in chunks)
    return n <= config.MAX_TURNING_SHARE * len(chunks) + 1e-9
