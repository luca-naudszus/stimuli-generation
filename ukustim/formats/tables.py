"""
tables.py
=============================
Note table and item table (build spec section 7), written as CSV, plus an empty assignment-table template
(one row per item; copied per participant and filled later). withheld_alternate (build spec v1.7) is 0 for
alternate-fingering items and blank for every other item; set it to 1 for alternates held back for the
new-fingering test (checklist item 17).

note_table.csv   one row per note of every item (listen-only items have empty string / fret / finger / motor columns)
item_table.csv   one row per item: type, key, base, composition, trained proportions, recombination type
assignment_template.csv   participant-specific columns left empty
"""

import csv
import os
from typing import Dict, List, Sequence

from ukustim import config
from ukustim.core import fretboard as fb
from ukustim.core import keys
from ukustim.core import versions as vs
from ukustim.core.items import Item
from ukustim.family.trained import Trained

NOTE_COLUMNS = ["item_id", "note_index", "pitch", "pitch_name", "string", "fret", "lh_finger", "hand_position",
                "onset_beat", "key", "scale_degree", "beat_in_bar", "bar_index", "musical_chunk_id",
                "abstract_chunk_id", "motor_chunk_id_aligned", "motor_chunk_id_misaligned",
                "motor_chunk_id_aligned_lh", "motor_chunk_id_misaligned_lh"]
ITEM_COLUMNS = ["item_id", "family_id", "layer", "variant_type", "key", "base_item_id", "misaligned_composition",
                "degree_of_misalignment", "prop_trained_musical", "prop_trained_motor_misaligned",
                "prop_trained_motor_aligned", "recombination_type", "musical_chunk_ids", "listen_only"]
ASSIGNMENT_COLUMNS = ["participant_id", "item_id", "family_id", "variant_type", "chunking_version", "design_group",
                      "difficulty_band", "intro_week_listening", "intro_week_playing", "withheld_alternate"]


def _motor_ids_per_note(item: Item, comp, mode: str = "full") -> List[str]:
    """For each of the 12 notes, the ID of the motor chunk it belongs to under the given composition."""
    out = [""] * config.N_NOTES
    for a, b, mid in vs.motor_chunks(item.positions, comp, mode):
        for i in range(a, b):
            out[i] = mid
    return out


def note_rows(item: Item) -> List[Dict]:
    """Rows of the note table for one item. Indexing: note_index 1..12, onset_beat 0..11, beat_in_bar 1..3,
    bar_index 1..4 (3/4, one musical chunk per bar). hand_position is always 1 (first position)."""
    n = config.CHUNK_LEN
    blank = [""] * config.N_NOTES
    ok_al = item.played
    ok_mi = item.played and bool(item.composition)
    al = _motor_ids_per_note(item, vs.aligned_composition()) if ok_al else blank
    mi = _motor_ids_per_note(item, item.composition) if ok_mi else blank
    al_lh = _motor_ids_per_note(item, vs.aligned_composition(), "lh") if ok_al else blank
    mi_lh = _motor_ids_per_note(item, item.composition, "lh") if ok_mi else blank
    rows = []
    for i in range(config.N_NOTES):
        p = item.positions[i] if item.played else None
        chunk = item.pitches[(i // n) * n:(i // n + 1) * n]
        rows.append(dict(
            item_id=item.item_id, note_index=i + 1, pitch=item.pitches[i], pitch_name=fb.pitch_name(item.pitches[i]),
            string=p.string if p else "", fret=p.fret if p else "", lh_finger=p.finger if p else "",
            hand_position=1 if p else "", onset_beat=i, key=item.key or "",
            scale_degree=keys.scale_degree(item.pitches[i], item.key),
            beat_in_bar=i % config.BEATS_PER_BAR + 1, bar_index=i // config.BEATS_PER_BAR + 1,
            musical_chunk_id=item.chunk_ids[i // n], abstract_chunk_id=keys.interval_pattern(chunk),
            motor_chunk_id_aligned=al[i], motor_chunk_id_misaligned=mi[i],
            motor_chunk_id_aligned_lh=al_lh[i], motor_chunk_id_misaligned_lh=mi_lh[i]))
    return rows


def _fmt(x):
    """Proportions rounded to 3 decimals; None (not applicable) -> empty cell."""
    return "" if x is None else round(x, 3)


def item_row(item: Item, trained: Trained) -> Dict:
    """One item-table row. The recombination type is derived again from the proportions (not taken from
    item.preserved), so the table always agrees with the numbers next to it."""
    p = trained.proportions(item)
    return dict(item_id=item.item_id, family_id=item.family_id, layer=item.layer, variant_type=item.variant_type,
                key=item.key or "", base_item_id=item.base_item_id,
                misaligned_composition=vs.comp_to_str(item.composition) if item.composition else "",
                degree_of_misalignment=vs.degree(item.composition) if item.composition else "",
                prop_trained_musical=_fmt(p["prop_trained_musical"]),
                prop_trained_motor_misaligned=_fmt(p["prop_trained_motor_misaligned"]),
                prop_trained_motor_aligned=_fmt(p["prop_trained_motor_aligned"]),
                recombination_type=trained.recombination_type(item) if item.variant_type == "recombined" else "",
                musical_chunk_ids="|".join(item.chunk_ids), listen_only=int(not item.played))


def assignment_row(item: Item) -> Dict:
    """Template row: item columns filled, participant columns empty; listen-only items are pre-marked."""
    return dict(participant_id="", item_id=item.item_id, family_id=item.family_id, variant_type=item.variant_type,
                chunking_version="", design_group="listen-only" if not item.played else "", difficulty_band="",
                intro_week_listening="", intro_week_playing="",
                withheld_alternate=0 if item.variant_type == "alternate fingering" else "")


def write_tables(items: Sequence[Item], outdir: str) -> None:
    """Write note_table.csv, item_table.csv and assignment_template.csv into outdir."""
    os.makedirs(outdir, exist_ok=True)
    trained = Trained(items)
    with open(os.path.join(outdir, "note_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, NOTE_COLUMNS)
        w.writeheader()
        for it in items:
            w.writerows(note_rows(it))
    with open(os.path.join(outdir, "item_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ITEM_COLUMNS)
        w.writeheader()
        for it in items:
            w.writerow(item_row(it, trained))
    with open(os.path.join(outdir, "assignment_template.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ASSIGNMENT_COLUMNS)
        w.writeheader()
        for it in items:
            w.writerow(assignment_row(it))
