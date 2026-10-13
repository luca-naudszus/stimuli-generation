"""
main.py
=============================
Pipeline runner.

    python main.py explore              # random sequences -> all features -> CSVs (output/)
    python main.py stimuli              # pool -> selection of sets A/B -> CSVs + report -> tab/MIDI export
    python main.py export               # only (re-)export tab/MIDI from stimuli/selected_*.csv
                                        # (e.g. after changing the timing in config.py)
Common options: --seed, --out-dir.  explore: --n-progressions, --n-melodies, --variant-mode.
stimuli: --save-pool also writes the full candidate pool as CSV.
"""

import argparse
import os
from typing import Dict, List

import config
from chord_vocab import CHORD_VOCAB, validate_chord_shapes
from tone_vocab import TONE_VOCAB
from generate_sequences import generate_progressions, generate_melodies
from evaluate import evaluate_progression, evaluate_melody, make_rows, write_csv


def run_explore(n_progressions: int, n_melodies: int, seed: int, out_dir: str, variant_mode: str) -> None:
    progs = generate_progressions(n_progressions, seed=seed, variant_mode=variant_mode)
    write_csv(os.path.join(out_dir, "progressions.csv"), make_rows("P", progs, CHORD_VOCAB, evaluate_progression))
    mels = generate_melodies(n_melodies, seed=seed, variant_mode=variant_mode)
    write_csv(os.path.join(out_dir, "melodies.csv"), make_rows("M", mels, TONE_VOCAB, evaluate_melody))
    print(f"{len(progs)} progressions -> {out_dir}/progressions.csv")
    print(f"{len(mels)} melodies     -> {out_dir}/melodies.csv")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    ex = sub.add_parser("explore")
    ex.add_argument("--n-progressions", type=int, default=config.N_PROGRESSIONS)
    ex.add_argument("--n-melodies", type=int, default=config.N_MELODIES)
    ex.add_argument("--variant-mode", choices=["optimal", "random"], default=config.VARIANT_MODE)
    ex.add_argument("--out-dir", default=config.OUTPUT_DIR)
    st = sub.add_parser("stimuli")
    st.add_argument("--save-pool", action="store_true")
    st.add_argument("--out-dir", default=config.STIMULI_DIR)
    exp = sub.add_parser("export")
    exp.add_argument("--out-dir", default=config.STIMULI_DIR)
    for p in (ex, st):
        p.add_argument("--seed", type=int, default=config.SEED)
    a = ap.parse_args()

    validate_chord_shapes()
    cmd = a.cmd or "explore"
    if cmd == "explore":
        if a.cmd is None:
            run_explore(config.N_PROGRESSIONS, config.N_MELODIES, config.SEED, config.OUTPUT_DIR, config.VARIANT_MODE)
        else:
            run_explore(a.n_progressions, a.n_melodies, a.seed, a.out_dir, a.variant_mode)
    elif cmd == "stimuli":
        from selection import run_selection
        from export_stimuli import export_all
        run_selection(save_pool=a.save_pool, seed=a.seed, out_dir=a.out_dir)
        export_all(a.out_dir)
    elif cmd == "export":
        from export_stimuli import export_all
        export_all(a.out_dir)


if __name__ == "__main__":
    main()