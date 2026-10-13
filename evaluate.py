"""
evaluate.py
=============================
Evaluates one sequence (physical + musical + variation features) and builds table rows.
"""

import csv
import os
from typing import Dict, List

from tone_vocab import TONE_VOCAB
from progression_features import progression_features
from melody_features import melody_features
from variation_check import variation_features_progression, variation_features_melody


def evaluate_progression(chord_ids: List[str]) -> Dict[str, float]:
    feats = progression_features(chord_ids)
    feats.update(variation_features_progression(chord_ids))
    return feats


def evaluate_melody(tone_ids: List[str]) -> Dict[str, float]:
    midi = [TONE_VOCAB[t]["midi"] for t in tone_ids]
    path = [TONE_VOCAB[t]["position"] for t in tone_ids]
    feats = melody_features(midi, path=path, leap_threshold=3)
    feats.update(variation_features_melody(tone_ids))
    return feats


def make_rows(prefix: str, sequences: List[List[str]], vocab: Dict, evaluate) -> List[Dict]:
    rows = []
    for k, ids in enumerate(sequences, start=1):
        row = dict(
            id=f"{prefix}{k:05d}",
            sequence=" | ".join(ids),
            labels=" ".join(vocab[i]["label"] for i in ids),
        )
        row.update(evaluate(ids))
        rows.append(row)
    return rows


def write_csv(path: str, rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})