"""
counts.py
=============================
Tier 1 feasibility report: chunks, junctions, chunk orders, valid bases (order x misaligned composition x
fingering) per degree of misalignment (build spec section 4). Called by `python main.py counts`.

For every degree, every chunk order is tried with every misaligned composition of that degree, and all neutral
fingerings are counted. Output fields per degree:
  order_x_composition    pairs tried
  valid                  pairs with at least one neutral fingering (= valid bases, without the fingering choice)
  fingering_assignments  valid bases counted with every fingering
  distinct_orders_valid  chunk orders that have at least one valid base
  chunks_used            chunks that occur in those orders
"""

from typing import Dict, Optional

from ukustim.core import chunks as ch
from ukustim.core import versions as vs
from ukustim.core.fingering import valid_assignments
from ukustim.core.inventory import Inventory


def count_report(inv: Optional[Inventory] = None, degrees=(1, 2, 3)) -> Dict:
    """Feasibility counts for the inventory as a whole and per degree of misalignment (see module docstring)."""
    inv = inv or Inventory()
    rep = dict(n_chunks=len(inv.chunks),
               n_monotonic=sum(ch.is_monotonic(c) for c in inv.chunks),
               n_junction_pairs=sum(len(v) for v in inv.graph.values()),
               n_chunk_orders=len(inv.tuples),
               n_fingering_options=sum(len(v) for v in inv.opts.values()),
               n_chunks_with_alt=sum(len(v) > 1 for v in inv.opts.values()),
               degrees={})
    for d in degrees:
        comps = vs.misaligned_compositions(d)
        n_pairs = n_with = n_assign = 0
        orders_ok = set()
        for t in inv.tuples:
            for comp in comps:
                n_pairs += 1
                k = sum(1 for _ in valid_assignments(t, comp, inv.opts))   # number of neutral fingerings
                if k:
                    n_with += 1
                    n_assign += k
                    orders_ok.add(t)
        used_chunks = {c for t in orders_ok for c in t}
        rep["degrees"][d] = dict(compositions=[vs.comp_to_str(c) for c in comps],
                                 order_x_composition=n_pairs, valid=n_with, fingering_assignments=n_assign,
                                 distinct_orders_valid=len(orders_ok), chunks_used=len(used_chunks))
    return rep
