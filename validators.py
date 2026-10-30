"""
validators.py
=============================
Automatic checks of build spec section 8 (checks 1-6). Every check returns Result objects, so a report
can show what was tested, not only what failed.

Item-level: 1 (frets / strings), 2 (neutrality), 3 (boundary cues), 5 (alternate), 6 (shift).
Set-level : 4 (recurrence), alternate-fingering consistency across items.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import config
import chunks as ch
import fretboard as fb
import versions as vs
from items import Item, Registry
from ukulele_geometry import OPEN_STRING_MIDI, STRING_ORDER


@dataclass
class Result:
    check: str          # '1' .. '6', or 'S' for structure
    item_id: str
    passed: bool
    message: str = ""

    def __str__(self):
        return f"[{'ok  ' if self.passed else 'FAIL'}] check {self.check:<3} {self.item_id:<14} {self.message}"


def _r(check, item, ok, msg_ok="", msg_fail=""):
    return Result(check, item.item_id if hasattr(item, "item_id") else str(item), ok, msg_ok if ok else msg_fail)


# ---------------------------------------------------------------------------
# Structure + check 1
# ---------------------------------------------------------------------------

def check_structure(item: Item) -> List[Result]:
    out = []
    ok = len(item.pitches) == config.N_NOTES and len(item.chunk_ids) == config.N_CHUNKS
    out.append(_r("S", item, ok, f"{config.N_NOTES} notes in {config.N_CHUNKS} chunks",
                  f"{len(item.pitches)} notes / {len(item.chunk_ids)} chunk IDs"))
    if item.composition:
        parts_ok = all(p in config.MOTOR_PARTS for p in item.composition) and sum(item.composition) == config.N_NOTES
        out.append(_r("S", item, parts_ok, f"composition {vs.comp_to_str(item.composition)}",
                      f"composition {item.composition} must use parts {config.MOTOR_PARTS} and sum to {config.N_NOTES}"))
    return out


def check_1_frets_strings(item: Item) -> List[Result]:
    if not item.played:
        return []
    out = []
    bad_fret = [i + 1 for i, p in enumerate(item.positions) if not 0 <= p.fret <= config.FRET_MAX]
    out.append(_r("1", item, not bad_fret, f"frets within 0-{config.FRET_MAX}",
                  f"notes {bad_fret} outside frets 0-{config.FRET_MAX}"))
    bad_pitch = [i + 1 for i, (p, m) in enumerate(zip(item.positions, item.pitches))
                 if OPEN_STRING_MIDI[p.string] + p.fret != m]
    out.append(_r("1", item, not bad_pitch, "positions produce the stated pitches",
                  f"notes {bad_pitch}: string/fret does not give the stated pitch"))
    span = fb.strings_adjacent_span(item.positions)
    out.append(_r("1", item, span <= config.MAX_STRING_SPAN,
                  f"{span} adjacent strings (max {config.MAX_STRING_SPAN})",
                  f"needs {span} adjacent strings (max {config.MAX_STRING_SPAN})"))
    bad_finger = [i + 1 for i, p in enumerate(item.positions) if (p.fret == 0) != (p.finger == 0)]
    out.append(_r("1", item, not bad_finger, "fingers consistent with open strings",
                  f"notes {bad_finger}: open string needs finger 0 and fretted note needs finger 1-4"))
    return out


# ---------------------------------------------------------------------------
# Check 2: neutrality
# ---------------------------------------------------------------------------

def check_2_neutrality(item: Item) -> List[Result]:
    if not item.played:
        return []
    if not item.composition:
        return [_r("2", item, False, "", "no misaligned composition given")]
    comp = item.composition
    out = []
    B, M = vs.boundaries(comp), vs.musical_boundaries()
    out.append(_r("2", item, B != M, f"misaligned composition {vs.comp_to_str(comp)} differs from aligned",
                  "composition equals the aligned chunking"))
    bad = sorted(vs.neutrality_violations(item.positions, comp))
    X = sorted(vs.string_crossings(item.positions))
    out.append(_r("2", item, not bad, f"string crossings {X} avoid M delta B {sorted(vs.forbidden_crossings(comp))}",
                  f"string crossings at transitions {bad} lie in M delta B {sorted(vs.forbidden_crossings(comp))}"))
    return out


# ---------------------------------------------------------------------------
# Check 3: boundary cues and chunk-internal rules
# ---------------------------------------------------------------------------

def check_3_cues(item: Item) -> List[Result]:
    if item.variant_type in ("string-pair shift",) or item.variant_type.startswith("probe"):
        return []
    out = []
    cps = item.chunk_pitches()
    for i, p in enumerate(cps):
        problems = ch.within_chunk_problems(p)
        out.append(_r("3", item, not problems, f"chunk {i + 1} clean",
                      f"chunk {i + 1} ({ch.chunk_id(p)}): " + "; ".join(problems)))
    for i in range(config.N_CHUNKS - 1):
        cues = ch.junction_cues(cps[i], cps[i + 1])
        t = config.CHUNK_LEN * (i + 1)
        out.append(_r("3", item, bool(cues), f"boundary {t}: cue {'+'.join(sorted(cues))}",
                      f"boundary {t} ({ch.chunk_id(cps[i])} | {ch.chunk_id(cps[i + 1])}): no boundary cue"))
    return out


# ---------------------------------------------------------------------------
# Check 5: alternate fingering (item vs its base)
# ---------------------------------------------------------------------------

def check_5_alternate(item: Item, base: Optional[Item]) -> List[Result]:
    if item.variant_type != "alternate fingering":
        return []
    if base is None:
        return [_r("5", item, False, "", "base item not found")]
    out = []
    out.append(_r("5", item, item.pitches == base.pitches, "all pitches kept", "pitches differ from the base"))
    moved = [i for i, (a, b) in enumerate(zip(base.positions, item.positions)) if a != b]
    out.append(_r("5", item, len(moved) >= config.ALT_MIN_NOTES_MOVED, f"{len(moved)} notes moved",
                  f"{len(moved)} notes moved (need >= {config.ALT_MIN_NOTES_MOVED})"))
    n = config.CHUNK_LEN
    chunks_moved = sorted({i // n + 1 for i in moved})
    out.append(_r("5", item, len(chunks_moved) >= config.ALT_MIN_CHUNKS, f"alternate fingering in chunks {chunks_moved}",
                  f"alternate fingering in {len(chunks_moved)} chunk(s) (need >= {config.ALT_MIN_CHUNKS})"))
    # only notes with a second position may move
    illegal = [i + 1 for i in moved if len(fb.positions_for_pitch(item.pitches[i])) < 2]
    out.append(_r("5", item, not illegal, "only notes with a second position moved",
                  f"notes {illegal} have no second position"))
    out.append(_r("5", item, item.chunk_ids == base.chunk_ids and item.composition == base.composition,
                  "musical chunk IDs and composition unchanged", "chunk IDs or composition differ from the base"))
    return out


# ---------------------------------------------------------------------------
# Check 6: string-pair shift
# ---------------------------------------------------------------------------

def check_6_shift(item: Item, base: Optional[Item]) -> List[Result]:
    if item.variant_type != "string-pair shift":
        return []
    if base is None:
        return [_r("6", item, False, "", "base item not found")]
    out = []
    same_frets = [p.fret for p in item.positions] == [p.fret for p in base.positions]
    out.append(_r("6", item, same_frets, "frets unchanged", "frets differ from the base"))
    deltas = {fb.string_index(a.string) - fb.string_index(b.string) for a, b in zip(item.positions, base.positions)}
    out.append(_r("6", item, len(deltas) == 1 and deltas <= {-1, 1},
                  f"one common string shift {sorted(deltas)}", f"strings not moved by one common step: {sorted(deltas)}"))
    same_fingers = [p.finger for p in item.positions] == [p.finger for p in base.positions]
    out.append(_r("6", item, same_fingers, "fingers unchanged", "fingers differ from the base"))
    new_pitch = [OPEN_STRING_MIDI[p.string] + p.fret for p in item.positions] == list(item.pitches)
    out.append(_r("6", item, new_pitch, "new pitches follow from the shifted strings", "pitches inconsistent with positions"))
    return out


# ---------------------------------------------------------------------------
# Item and set validation
# ---------------------------------------------------------------------------

def validate_item(item: Item, items_by_id: Dict[str, Item]) -> List[Result]:
    base = items_by_id.get(item.base_item_id)
    return (check_structure(item) + check_1_frets_strings(item) + check_2_neutrality(item)
            + check_3_cues(item) + check_5_alternate(item, base) + check_6_shift(item, base))


def check_4_recurrence(items: Sequence[Item]) -> List[Result]:
    """Set level. (a) every inventory chunk used by the bases occurs in >= 2 bases;
    (b) every misaligned base shares >= 1 crossing motor chunk (same content) with another base."""
    bases = [i for i in items if i.variant_type == "base"]
    out: List[Result] = []
    if not bases:
        return [Result("4", "set", False, "no base items")]
    if len(bases) < config.N_BASES:
        out.append(Result("4", "set", False, f"{len(bases)} bases (need >= {config.N_BASES})"))
    counts: Dict[str, int] = {}
    for b in bases:
        for cid in set(b.chunk_ids):
            counts[cid] = counts.get(cid, 0) + 1
    for cid, n in sorted(counts.items()):
        out.append(Result("4", cid, n >= 2, f"musical chunk in {n} bases" if n >= 2 else f"musical chunk in only {n} base"))
    # fingering consistency of chunks across all played items with the same chunk ID and no alternate use
    # (each musical chunk is fingered identically wherever it recurs, except in alternate items)
    seen: Dict[str, tuple] = {}
    for it in items:
        if not it.played or it.variant_type in ("alternate fingering", "string-pair shift"):
            continue
        for cid, pos in zip(it.chunk_ids, it.chunk_positions()):
            if cid.startswith("new:"):
                continue
            if cid in seen and seen[cid] != pos:
                out.append(Result("4", it.item_id, False, f"chunk {cid} fingered differently than elsewhere"))
            seen.setdefault(cid, pos)
    # alternate fingering identical wherever the chunk appears in alternate items
    alt_seen: Dict[str, tuple] = {}
    for it in items:
        if it.variant_type != "alternate fingering":
            continue
        for cid, pos in zip(it.chunk_ids, it.chunk_positions()):
            if cid in seen and pos != seen[cid]:
                if cid in alt_seen and alt_seen[cid] != pos:
                    out.append(Result("5", it.item_id, False, f"chunk {cid}: alternate fingering differs between alternate items"))
                alt_seen.setdefault(cid, pos)
    # minimum rule for crossing motor chunks (misaligned version)
    crossing = {b.item_id: vs.crossing_motor_ids(b.positions, b.composition) for b in bases}
    all_motor = {b.item_id: {m for _, _, m in vs.motor_chunks(b.positions, b.composition)} for b in bases}
    for b in bases:
        others = set().union(*[all_motor[o.item_id] for o in bases if o is not b]) if len(bases) > 1 else set()
        shared = crossing[b.item_id] & others
        out.append(Result("4", b.item_id, bool(shared),
                          f"shares {len(shared)} crossing motor chunk(s) with other bases" if shared
                          else "shares no crossing motor chunk with another base"))
    return out


def validate_set(items: Sequence[Item]) -> List[Result]:
    by_id = {i.item_id: i for i in items}
    out: List[Result] = []
    for it in items:
        out.extend(validate_item(it, by_id))
    out.extend(check_4_recurrence(items))
    return out


def summarize(results: Sequence[Result]) -> str:
    fails = [r for r in results if not r.passed]
    lines = [f"{len(results)} checks, {len(fails)} failed"]
    lines += [str(r) for r in fails]
    return "\n".join(lines)
