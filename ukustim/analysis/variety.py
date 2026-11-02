"""
variety.py
=============================
Variety of the bases (build spec section 3, Q7 step 3): different compositions across bases, shared musical chunks
at different positions, and which motor chunks recur. Report only; the search objective uses the composition count.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Sequence

from ukustim.core import versions as vs
from ukustim.core.items import Item


def variety_report(items: Sequence[Item]) -> Dict:
    bases = [i for i in items if i.variant_type == "base" and i.played]
    comps = Counter(vs.comp_to_str(b.composition) for b in bases)
    positions = defaultdict(set)
    uses = Counter()
    for b in bases:
        for k, cid in enumerate(b.chunk_ids):
            positions[cid].add(k + 1)
            uses[cid] += 1
    motor_uses = Counter()
    for b in bases:
        for _, _, m in vs.motor_chunks(b.positions, b.composition):
            motor_uses[m] += 1
    crossing = Counter()
    for b in bases:
        for m in vs.crossing_motor_ids(b.positions, b.composition):
            crossing[m] += 1
    return dict(compositions=dict(comps), chunk_positions={c: sorted(p) for c, p in positions.items()},
                chunk_uses=dict(uses), n_chunks_at_several_positions=sum(len(p) > 1 for p in positions.values()),
                n_motor_chunks=len(motor_uses), n_motor_chunks_recurring=sum(v > 1 for v in motor_uses.values()),
                n_crossing_chunks=len(crossing), n_crossing_chunks_recurring=sum(v > 1 for v in crossing.values()))


def format_variety(rep: Dict) -> str:
    lines = ["Variety of the bases:",
             "  compositions: " + ", ".join(f"{c} x{n}" for c, n in rep["compositions"].items()),
             f"  trained chunks at more than one position: {rep['n_chunks_at_several_positions']} of {len(rep['chunk_positions'])}",
             "  chunk (uses; positions): " + "; ".join(f"{c} ({rep['chunk_uses'][c]}; {','.join(map(str, p))})"
                                                       for c, p in sorted(rep["chunk_positions"].items())),
             f"  motor chunks (misaligned, full): {rep['n_motor_chunks']} distinct, {rep['n_motor_chunks_recurring']} recur in >= 2 bases",
             f"  crossing motor chunks: {rep['n_crossing_chunks']} distinct, {rep['n_crossing_chunks_recurring']} recur in >= 2 bases"]
    return "\n".join(lines)
