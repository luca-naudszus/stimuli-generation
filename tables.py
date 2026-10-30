"""
tables.py
=============================
Note table and item table (build spec section 7), written as CSV.
The assignment table is filled later (per participant) and is not produced here.
"""

import csv
import os
from typing import Dict, List, Sequence

import config
import versions as vs
from items import Item

NOTE_COLUMNS = ["item_id", "note_index", "pitch", "pitch_name", "string", "fret", "lh_finger", "hand_position",
                "onset_beat", "musical_chunk_id", "motor_chunk_id_aligned", "motor_chunk_id_misaligned"]
ITEM_COLUMNS = ["item_id", "family_id", "layer", "variant_type", "base_item_id", "misaligned_composition",
                "degree_of_misalignment", "preserved_chunks", "musical_chunk_ids", "listen_only"]


def _motor_ids_per_note(item: Item, comp) -> List[str]:
    out = [""] * config.N_NOTES
    for a, b, mid in vs.motor_chunks(item.positions, comp):
        for i in range(a, b):
            out[i] = mid
    return out


def note_rows(item: Item) -> List[Dict]:
    import fretboard as fb
    n = config.CHUNK_LEN
    al = _motor_ids_per_note(item, vs.aligned_composition()) if item.played else [""] * config.N_NOTES
    mi = _motor_ids_per_note(item, item.composition) if item.played and item.composition else [""] * config.N_NOTES
    rows = []
    for i in range(config.N_NOTES):
        p = item.positions[i] if item.played else None
        rows.append(dict(
            item_id=item.item_id, note_index=i + 1, pitch=item.pitches[i], pitch_name=fb.pitch_name(item.pitches[i]),
            string=p.string if p else "", fret=p.fret if p else "", lh_finger=p.finger if p else "",
            hand_position=1 if p else "", onset_beat=i,
            musical_chunk_id=item.chunk_ids[i // n], motor_chunk_id_aligned=al[i], motor_chunk_id_misaligned=mi[i]))
    return rows


def item_row(item: Item) -> Dict:
    return dict(item_id=item.item_id, family_id=item.family_id, layer=item.layer, variant_type=item.variant_type,
                base_item_id=item.base_item_id,
                misaligned_composition=vs.comp_to_str(item.composition) if item.composition else "",
                degree_of_misalignment=vs.degree(item.composition) if item.composition else "",
                preserved_chunks=item.preserved, musical_chunk_ids="|".join(item.chunk_ids),
                listen_only=int(not item.played))


def write_tables(items: Sequence[Item], outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "note_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, NOTE_COLUMNS)
        w.writeheader()
        for it in items:
            w.writerows(note_rows(it))
    with open(os.path.join(outdir, "item_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ITEM_COLUMNS)
        w.writeheader()
        for it in items:
            w.writerow(item_row(it))
