"""
loader.py
=============================
Hand-built input as two CSV files (editable in a spreadsheet):

chunks.csv  chunk_id (optional; default = pitch names), fingering, alt_fingering (optional), role
            fingering = three positions 'C0 C2 E0' (string+fret, optional '/finger': 'C2/3')
            role      = trained | new   (new chunks get the ID prefix 'new:')
items.csv   item_id, family_id, layer, variant_type, chunks, composition, preserved
            chunks = chunk IDs separated by spaces; composition e.g. 3-2-2-3-2 (misaligned motor chunks)
            variant_type: base | recombined | mixed | new-chunk
            preserved = recombination type as recorded (musical-only | motor-only | both); the item table derives
            the type again from the trained proportions.
            Alternate fingerings, string-pair shifts, played transpositions and probes are generated from the
            bases automatically.

Round trip: the search saves its best set with save_set (only the hand-editable items: bases and generalization
items), and `python main.py check DIR` reads it back with load_set, which regenerates the family members from the
bases and the registry. Edit the CSVs by hand, run check again, and every rule is re-validated.
"""

import csv
import os
from typing import Dict, List, Tuple

from ukustim import config
from ukustim.core import chunks as ch
from ukustim.core import fretboard as fb
from ukustim.core import items as it
from ukustim.core import versions as vs
from ukustim.core.items import ChunkDef, Item, Registry
from ukustim.family import alternate, probes, string_shift, transposition


def _read(path):
    """CSV rows as dicts (header = keys)."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_registry(path: str) -> Registry:
    """chunks.csv -> registry. Pitches follow from the fingering; the ID defaults to the pitch names ('new:' added
    for role 'new'). An alternate fingering must give the same pitches."""
    reg: Registry = {}
    for row in _read(path):
        fing = tuple(fb.parse_position(t) for t in row["fingering"].split())
        alt = tuple(fb.parse_position(t) for t in row.get("alt_fingering", "").split()) or None
        role = (row.get("role") or "trained").strip()
        pitches = tuple(fb.pitch_of(p.string, p.fret) for p in fing)
        cid = (row.get("chunk_id") or "").strip() or ch.chunk_id(pitches)
        if role == "new" and not cid.startswith("new:"):
            cid = "new:" + cid
        if alt is not None and tuple(fb.pitch_of(p.string, p.fret) for p in alt) != pitches:
            raise ValueError(f"chunk {cid}: alternate fingering changes the pitches")
        reg[cid] = ChunkDef(cid, pitches, fing, alt, role)
    return reg


def load_items(path: str, reg: Registry) -> List[Item]:
    """items.csv -> items, built from the registry (build_item), so the fingering comes from chunks.csv."""
    out = []
    for row in _read(path):
        ids = row["chunks"].split()
        missing = [c for c in ids if c not in reg]
        if missing:
            raise ValueError(f"item {row['item_id']}: unknown chunk IDs {missing}")
        comp = vs.comp_from_str(row["composition"]) if row.get("composition") else ()
        layer = row.get("layer") or ("family" if row["variant_type"] == "base" else "generalization")
        out.append(it.build_item(row["item_id"], row.get("family_id") or "F?", layer, row["variant_type"],
                                 ids, reg, comp, preserved=row.get("preserved", "")))
    return out


def with_family_members(items: List[Item], reg: Registry, with_probes: bool = True) -> Tuple[List[Item], List[str]]:
    """Add alternate fingering, string-pair shift, played transposition and probes for every base.
    The same builders as selection/assemble.assemble_family, so a loaded set gets exactly the family members the
    search would build (the alternates come from the registry's alt_fingering). Returns (items, notes)."""
    out, notes = [], []
    for b in items:
        out.append(b)
        if b.variant_type != "base":
            continue
        a = alternate.alternate_item(b, reg)
        if a:
            out.append(a)
        else:
            notes.append(f"{b.item_id}: no valid alternate fingering")
        s = string_shift.string_pair_shift(b)
        if s:
            out.append(s)
        else:
            notes.append(f"{b.item_id}: string-pair shift impossible")
        t, why = transposition.played_transposition(b, reg)
        if t:
            out.append(t)
        else:
            notes.append(f"{b.item_id}: played transposition to {config.TRANSPOSITION_KEY} impossible ({why})")
        if with_probes:
            out.extend(probes.all_probes(b))
    return out, notes


def load_set(directory: str, with_probes: bool = True) -> Tuple[List[Item], Registry, List[str]]:
    """Read a set folder (chunks.csv + items.csv) and generate its family members. Returns (items, registry, notes)."""
    reg = load_registry(os.path.join(directory, "chunks.csv"))
    base_items = load_items(os.path.join(directory, "items.csv"), reg)
    items, notes = with_family_members(base_items, reg, with_probes)
    return items, reg, notes


def save_set(items: List[Item], reg: Registry, directory: str) -> None:
    """Write chunks.csv and items.csv for the hand-editable items (bases, recombined, mixed, new-chunk)."""
    os.makedirs(directory, exist_ok=True)
    used = set()
    # only these variant types are stored; the rest is regenerated on load
    listed = [i for i in items if i.variant_type in ("base", "recombined", "mixed", "new-chunk")]
    for i in listed:
        used.update(i.chunk_ids)
    with open(os.path.join(directory, "chunks.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chunk_id", "fingering", "alt_fingering", "role"])
        for cid in sorted(used):
            d = reg[cid]
            w.writerow([cid, " ".join(p.label() for p in d.fingering),
                        " ".join(p.label() for p in d.alt) if d.alt else "", d.role])
    with open(os.path.join(directory, "items.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "family_id", "layer", "variant_type", "chunks", "composition", "preserved"])
        for i in listed:
            w.writerow([i.item_id, i.family_id, i.layer, i.variant_type, " ".join(i.chunk_ids),
                        vs.comp_to_str(i.composition), i.preserved])
