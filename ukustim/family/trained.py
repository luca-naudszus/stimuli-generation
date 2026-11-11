"""
trained.py
=============================
What counts as 'trained' in a set, and the proportions the item table records (build spec section 7, Q10):
prop_trained_musical, prop_trained_motor_misaligned, prop_trained_motor_aligned, and the recombination type
derived from them. 'Trained' = occurs in a base item of the set (musical chunk ID; motor chunk content).

- Musical chunks are matched by ID, so 'new:' chunks never count as trained.
- Motor chunks are matched by their 'full' ID (string, fret, finger), so an item made of new musical chunks can still
  contain trained motor chunks (short 2-note pieces often recur by accident).
- Only BASES count as trained, not trained variants (alternates, shifts, transpositions); see Q18.
"""

from typing import Dict, Optional, Sequence, Set

from ukustim.core import versions as vs
from ukustim.core.items import Item, is_trained_id


class Trained:
    """What the participants practise in this set: three sets of IDs collected from the bases.
      musical        musical chunk IDs of the bases
      motor_misal    'full' motor chunk IDs of the bases, each cut by its own misaligned composition
      motor_aligned  'full' motor chunk IDs of the bases, cut 3-3-3-3
    Each base exists in both chunking versions for the prototype, so both motor sets are 'trained' (in its version)."""

    def __init__(self, items: Sequence[Item]):
        bases = [i for i in items if i.variant_type == "base" and i.played]
        self.musical: Set[str] = {c for b in bases for c in b.chunk_ids}
        self.motor_misal: Set[str] = {m for b in bases if b.composition
                                      for _, _, m in vs.motor_chunks(b.positions, b.composition)}
        self.motor_aligned: Set[str] = {m for b in bases
                                        for _, _, m in vs.motor_chunks(b.positions, vs.aligned_composition())}

    def proportions(self, item: Item) -> Dict[str, Optional[float]]:
        """Share of the item's chunks that are trained: musical (of 4), misaligned motor (of the item's 5 or 6
        motor chunks under its own composition), aligned motor (of 4). Listen-only items have no motor proportions."""
        pm = sum(1 for c in item.chunk_ids if is_trained_id(c) and c in self.musical) / len(item.chunk_ids)
        if not item.played:
            return dict(prop_trained_musical=pm, prop_trained_motor_misaligned=None, prop_trained_motor_aligned=None)
        al = [m for _, _, m in vs.motor_chunks(item.positions, vs.aligned_composition())]
        mi = [m for _, _, m in vs.motor_chunks(item.positions, item.composition)] if item.composition else []
        return dict(prop_trained_musical=pm,
                    prop_trained_motor_aligned=sum(m in self.motor_aligned for m in al) / len(al),
                    prop_trained_motor_misaligned=(sum(m in self.motor_misal for m in mi) / len(mi)) if mi else None)

    def recombination_type(self, item: Item) -> str:
        """musical-only | motor-only | both | neither, from the proportions (misaligned version).
        A type needs a proportion of exactly 1: 'musical-only' = every musical chunk trained, at least one motor
        chunk not; 'motor-only' = the reverse. '' for items without a misaligned composition."""
        p = self.proportions(item)
        pm, pmo = p["prop_trained_musical"], p["prop_trained_motor_misaligned"]
        if pmo is None:
            return ""
        if pm == 1 and pmo == 1:
            return "both"
        if pm == 1:
            return "musical-only"
        if pmo == 1:
            return "motor-only"
        return "neither"
