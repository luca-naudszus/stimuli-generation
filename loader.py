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
            Alternate fingerings, string-pair shifts and probes are generated from the bases automatically.
"""

import csv
import os
from typing import Dict, List, Tuple

import config
import chunks as ch
import fretboard as fb
import items as it
import versions as vs
from items import ChunkDef, Item, Registry


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_registry(path: str) -> Registry:
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


def with_family_members(items: List[Item], reg: Registry, probes: bool = True) -> Tuple[List[Item], List[str]]:
    """Add alternate fingering, string-pair shift and probes for every base."""
    out, notes = [], []
    for b in items:
        out.append(b)
        if b.variant_type != "base":
            continue
        a = it.alternate_item(b, reg)
        if a:
            out.append(a)
        else:
            notes.append(f"{b.item_id}: no valid alternate fingering")
        s = it.string_pair_shift(b)
        if s:
            out.append(s)
        else:
            notes.append(f"{b.item_id}: string-pair shift impossible")
        if probes:
            out.extend(it.all_probes(b))
    return out, notes


def load_set(directory: str, probes: bool = True) -> Tuple[List[Item], Registry, List[str]]:
    reg = load_registry(os.path.join(directory, "chunks.csv"))
    base_items = load_items(os.path.join(directory, "items.csv"), reg)
    items, notes = with_family_members(base_items, reg, probes)
    return items, reg, notes


def save_set(items: List[Item], reg: Registry, directory: str) -> None:
    """Write chunks.csv and items.csv for the hand-editable items (bases, recombined, mixed, new-chunk)."""
    os.makedirs(directory, exist_ok=True)
    used = set()
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
