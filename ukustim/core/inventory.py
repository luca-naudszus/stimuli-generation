"""
inventory.py
=============================
The musical-chunk inventory: all valid chunks over the key's pitches, the junction graph (which chunk may
follow which, with a boundary cue), fingering options per chunk, and all valid chunk orders.

One Inventory is built per run (it depends only on config) and passed to the search, the family assembly and the
counts. It caches everything that is the same for every set, so the expensive enumerations happen once.
"""

from typing import Dict, List, Tuple

from ukustim.core import chunks as ch

Chunk = Tuple[int, ...]


class Inventory:
    """Attributes:
      chunks  every valid musical chunk (pitch tuples; 12 under the strict rule)
      graph   chunk -> chunks that may FOLLOW it (boundary cue at the junction)
      preds   chunk -> chunks that may PRECEDE it (the graph reversed; used by the exact-cover search to find chunks
              that can connect to a partial set from either side)
      opts    chunk -> list of FingeringOption (every way to play it in first position); option indices used in
              assignments and in `fixed` refer to these lists
      tuples  every chunk order (4 distinct chunks, cue at every junction); computed on first use"""

    def __init__(self):
        self.chunks: List[Chunk] = ch.enumerate_chunks()
        self.graph = ch.junction_graph(self.chunks)
        self.opts = {c: ch.fingering_options(c) for c in self.chunks}
        self._tuples = None
        # reverse the junction graph: for every edge a -> b, record a as a predecessor of b
        preds: Dict[Chunk, List[Chunk]] = {c: [] for c in self.chunks}
        for a, bs in self.graph.items():
            for b in bs:
                preds[b].append(a)
        self.preds = preds

    @property
    def tuples(self):
        """All ordered N_CHUNKS-tuples of chunks with a boundary cue at every junction (2,476 under the strict rule).
        Computed lazily and cached, since not every command needs them."""
        if self._tuples is None:
            self._tuples = ch.enumerate_chunk_tuples(self.chunks, self.graph)
        return self._tuples

    def turning(self, c: Chunk) -> bool:
        """True for an X-Y-X chunk (only possible when TURNING_POINT_CHUNKS = 'allow')."""
        return ch.has_turning_point(c)
