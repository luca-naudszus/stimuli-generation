"""
inventory.py
=============================
The musical-chunk inventory: all valid chunks over the key's pitches, the junction graph (which chunk may
follow which, with a boundary cue), fingering options per chunk, and all valid chunk orders.
"""

from typing import Dict, List, Tuple

from ukustim.core import chunks as ch

Chunk = Tuple[int, ...]


class Inventory:
    def __init__(self):
        self.chunks: List[Chunk] = ch.enumerate_chunks()
        self.graph = ch.junction_graph(self.chunks)
        self.opts = {c: ch.fingering_options(c) for c in self.chunks}
        self._tuples = None
        preds: Dict[Chunk, List[Chunk]] = {c: [] for c in self.chunks}
        for a, bs in self.graph.items():
            for b in bs:
                preds[b].append(a)
        self.preds = preds

    @property
    def tuples(self):
        """All ordered N_CHUNKS-tuples of chunks with a boundary cue at every junction."""
        if self._tuples is None:
            self._tuples = ch.enumerate_chunk_tuples(self.chunks, self.graph)
        return self._tuples

    def turning(self, c: Chunk) -> bool:
        return ch.has_turning_point(c)
