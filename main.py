"""
main.py
=============================
Pipeline runner: generate n progressions and n melodies, evaluate all features
(physical, musical, variation check) and write one CSV per type.

    python main.py                       # sizes/lengths/seed from config.py
    python main.py --n-progressions 500 --n-melodies 100 --seed 7
"""

import argparse
import csv
import os
from typing import Dict, List

import config
from chord_vocab import CHORD_VOCAB, validate_chord_shapes
from tone_vocab import TONE_VOCAB
from generate_sequences import generate_progressions, generate_melodies
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


def _rows(prefix: str, sequences: List[List[str]], vocab: Dict, evaluate) -> List[Dict]:
    rows = []
    for k, ids in enumerate(sequences, start=1):
        row = dict(
            id=f"{prefix}{k:04d}",
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


def run(n_progressions: int, n_melodies: int, seed: int, out_dir: str) -> None:
    validate_chord_shapes()

    progs = generate_progressions(n_progressions, seed=seed)
    prog_rows = _rows("P", progs, CHORD_VOCAB, evaluate_progression)
    write_csv(os.path.join(out_dir, "progressions.csv"), prog_rows)

    mels = generate_melodies(n_melodies, seed=seed)
    mel_rows = _rows("M", mels, TONE_VOCAB, evaluate_melody)
    write_csv(os.path.join(out_dir, "melodies.csv"), mel_rows)

    print(f"{len(prog_rows)} progressions -> {out_dir}/progressions.csv")
    print(f"{len(mel_rows)} melodies     -> {out_dir}/melodies.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-progressions", type=int, default=config.N_PROGRESSIONS)
    ap.add_argument("--n-melodies", type=int, default=config.N_MELODIES)
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--out-dir", default=config.OUTPUT_DIR)
    a = ap.parse_args()
    run(a.n_progressions, a.n_melodies, a.seed, a.out_dir)