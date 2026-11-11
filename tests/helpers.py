"""Shared test helpers: expect(), and a cached valid set (one solution assembled into a full family).

The tests use no framework: each test module has a run() function that calls expect(name, condition) for every
check; expect prints PASS / FAIL and records failures in FAILED, and run_all.py prints the total. Most tests build
on fixture(), a real set found by the exhaustive search, so they exercise the same code paths as the CLI.
"""

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ukustim import config  # noqa: E402

FAILED = []


def expect(name, cond, detail=""):
    """Record one check; `detail` is printed only on failure."""
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


def failing_checks(results):
    """Check numbers ('1', '2', ...) that failed in a list of validator Results; used to test that a deliberately
    broken item fails exactly the intended check."""
    return sorted({r.check for r in results if not r.passed})


_FX = None


def fixture():
    """A valid degree-2 set (3 bases) with its whole family, built once (cached in _FX).
    Attributes: inv, sol, items, reg, notes, by_id, base (B1), alt (B1-alt or None), shift (B1-shift or None)."""
    global _FX
    if _FX is None:
        from ukustim.core.inventory import Inventory
        from ukustim.selection import exact_cover as ec
        from ukustim.selection.assemble import assemble_family
        config.MISALIGNMENT_DEGREE = 2
        inv = Inventory()
        sols, _ = ec.find_sets_exhaustive(inv, 2, max_tries=800, want=1)
        items, reg, notes = assemble_family(inv, sols[0])
        by_id = {i.item_id: i for i in items}
        _FX = SimpleNamespace(inv=inv, sol=sols[0], items=items, reg=reg, notes=notes, by_id=by_id,
                              base=by_id["B1"], alt=by_id.get("B1-alt"), shift=by_id.get("B1-shift"))
    return _FX


def transposable_base(key="D"):
    """(base item, registry) for a valid base that can be transposed to `key` (the G set has almost none, Q11).
    The registry is empty, so played_transposition registers the transposed chunks from scratch."""
    from ukustim.core import fretboard as fb
    from ukustim.core.fingering import positions_of
    from ukustim.core.inventory import Inventory
    from ukustim.core.items import item_from_positions
    from ukustim.family.transposition import has_transposition
    from ukustim.selection import objective_search as osr
    from ukustim.core import chunks as ch
    inv = fixture().inv
    old = config.TRANSPOSITION_KEY
    config.TRANSPOSITION_KEY = key
    try:
        for c in osr.candidates(inv, 2):
            if c.transposable:
                pos = positions_of(c.order, c.assign, inv.opts)
                b = item_from_positions("T1", "FT", "family", "base", pos, c.comp,
                                        chunk_ids=[ch.chunk_id(x) for x in c.order])
                return b, {}
    finally:
        config.TRANSPOSITION_KEY = old
    raise RuntimeError("no transposable base found")
