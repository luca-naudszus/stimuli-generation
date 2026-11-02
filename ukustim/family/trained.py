"""
trained.py
=============================
What counts as 'trained' in a set, and the proportions the item table records (build spec section 7, Q10):
prop_trained_musical, prop_trained_motor_misaligned, prop_trained_motor_aligned, and the recombination type
derived from them. 'Trained' = occurs in a base item of the set (musical chunk ID; motor chunk content).
"""

from typing import Dict, Optional, Sequence, Set

from ukustim.core import versions as vs
from ukustim.core.items import Item, is_trained_id


class Trained:
    def __init__(self, items: Sequence[Item]):
        bases = [i for i in items if i.variant_type == "base" and i.played]
        self.musical: Set[str] = {c for b in bases for c in b.chunk_ids}
        self.motor_misal: Set[str] = {m for b in bases if b.composition
                                      for _, _, m in vs.motor_chunks(b.positions, b.composition)}
        self.motor_aligned: Set[str] = {m for b in bases
                                        for _, _, m in vs.motor_chunks(b.positions, vs.aligned_composition())}

    def proportions(self, item: Item) -> Dict[str, Optional[float]]:
        pm = sum(1 for c in item.chunk_ids if is_trained_id(c) and c in self.musical) / len(item.chunk_ids)
        if not item.played:
            return dict(prop_trained_musical=pm, prop_trained_motor_misaligned=None, prop_trained_motor_aligned=None)
        al = [m for _, _, m in vs.motor_chunks(item.positions, vs.aligned_composition())]
        mi = [m for _, _, m in vs.motor_chunks(item.positions, item.composition)] if item.composition else []
        return dict(prop_trained_musical=pm,
                    prop_trained_motor_aligned=sum(m in self.motor_aligned for m in al) / len(al),
                    prop_trained_motor_misaligned=(sum(m in self.motor_misal for m in mi) / len(mi)) if mi else None)

    def recombination_type(self, item: Item) -> str:
        """musical-only | motor-only | both | neither, from the proportions (misaligned version)."""
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
