"""
main.py
=============================
Subcommands
  counts                       Tier-1 feasibility counts per degree of misalignment
  search [--degree D]          Tier-2 search for complete prototype sets; builds the best one
  check DIR                    validate a hand-built set (chunks.csv + items.csv) and report separability
  cues DIR [--png --svg --pdf] LilyPond tab cues (participant / researcher) for a hand-built set
All outputs go to config.OUTPUT_DIR.
"""

import argparse
import json
import os
import sys

import config
import cues
import difficulty as dif
import export as ex
import feasibility as fz
import loader
import rdm
import tables
import validators as val
import versions as vs


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def report_set(items, reg, notes, outdir, inv=None, title=""):
    """Validate, score, write tables / tabs / MIDI / RDM report for a list of items."""
    os.makedirs(outdir, exist_ok=True)
    results = val.validate_set(items)
    lines = [title, val.summarize(results), ""]
    if notes:
        lines += ["Notes:"] + ["  " + n for n in notes] + [""]
    played = [i for i in items if i.played]
    inv = inv or fz.Inventory()
    model = dif.DifficultyModel.fit(fz.reference_items(inv, 1500, deg=config.MISALIGNMENT_DEGREE))
    by_id = {i.item_id: i for i in items}
    lines.append("Difficulty (mean z-score over the reference sample of valid bases):")
    for i in played:
        s = model.score(i)
        gap = ""
        if i.variant_type == "alternate fingering" and i.base_item_id in by_id:
            gap = f"   gap to base {s - model.score(by_id[i.base_item_id]):+.2f}"
        lines.append(f"  {i.item_id:<10} {i.variant_type:<20} {s:+.2f}{gap}")
    rep = rdm.correlation_report(items)
    lines += ["", rdm.format_report(rep)]
    _write(os.path.join(outdir, "report.txt"), "\n".join(lines) + "\n")
    rdm.save_heatmap(rep, os.path.join(outdir, "rdm_correlations.png"))
    tables.write_tables(items, outdir)
    ex.export_items(items, os.path.join(outdir, "stimuli"))
    cues.export_cues(items, os.path.join(outdir, "cues"))      # .ly sources only; `main.py cues DIR --png` renders
    return results, rep


def cmd_counts(args):
    inv = fz.Inventory()
    rep = fz.count_report(inv)
    _write(os.path.join(config.OUTPUT_DIR, "feasibility_counts.json"), json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def cmd_search(args):
    inv = fz.Inventory()
    degrees = [args.degree] if args.degree else [1, 2, 3]
    summary, best = {}, None
    lines = [f"Set search (exhaustive over exact-cover triples: {config.N_BASES} bases, {config.N_TRAINED_CHUNKS} chunks, "
             f"each chunk in exactly 2 bases). Up to {args.max_tries} triples tried per degree, {args.eval} feasible sets scored."]
    for d in degrees:
        sols, stats = fz.find_sets_exhaustive(inv, d, max_tries=args.max_tries, want=args.eval)
        scored = []
        for k, sol in enumerate(sols):
            items, reg, notes = fz.assemble_family(inv, sol, seed=k)
            rep = rdm.correlation_report(items)
            scored.append((not notes, rdm.separability_score(rep), k, sol, items, reg, notes))
        scored.sort(key=lambda x: (not x[0], x[1]))
        sc = [x[1] for x in scored]
        summary[d] = dict(stats=stats, scored=len(scored), best_max_abs_r=min(sc) if sc else None,
                          median_max_abs_r=sorted(sc)[len(sc) // 2] if sc else None)
        lines.append(f"degree {d}: {stats}; max |r| over key pairs, best {summary[d]['best_max_abs_r']}, median {summary[d]['median_max_abs_r']}")
        print(lines[-1])
        if scored and d == config.MISALIGNMENT_DEGREE:
            best = (d, scored[0])
    _write(os.path.join(config.OUTPUT_DIR, "feasibility_search.txt"), "\n".join(lines) + "\n")
    _write(os.path.join(config.OUTPUT_DIR, "feasibility_search.json"), json.dumps(summary, indent=1, default=str))
    if best is None:
        print(f"no complete set at the default degree {config.MISALIGNMENT_DEGREE}")
        return
    d, (complete, score, k, sol, items, reg, notes) = best
    outdir = os.path.join(config.OUTPUT_DIR, f"prototype_degree{d}")
    results, rep = report_set(items, reg, notes, outdir, inv,
                              f"Prototype set found by search, degree {d}; max |r| over key pairs {score:.2f}")
    loader.save_set(items, reg, os.path.join(outdir, "input"))
    print(f"best set written to {outdir}; checks failed: {sum(not r.passed for r in results)}; max|r| {score:.2f}")


def cmd_check(args):
    items, reg, notes = loader.load_set(args.dir)
    outdir = os.path.join(config.OUTPUT_DIR, "check_" + os.path.basename(os.path.normpath(args.dir)))
    results, rep = report_set(items, reg, notes, outdir, title=f"Hand-built set {args.dir}")
    print(val.summarize(results))
    print(rdm.format_report(rep))


def cmd_cues(args):
    items, reg, notes = loader.load_set(args.dir)
    outdir = os.path.join(config.OUTPUT_DIR, "cues_" + os.path.basename(os.path.normpath(args.dir)))
    fmts = [f for f in ("png", "svg", "pdf") if getattr(args, f)]
    cues.export_cues(items, outdir, fmts, show_fingers=not args.no_fingers)
    print(f"cue sources{' and ' + '/'.join(fmts) if fmts else ''} written to {outdir}/participant and /researcher")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("counts")
    s = sub.add_parser("search")
    s.add_argument("--degree", type=int)
    s.add_argument("--max-tries", type=int, default=3000, dest="max_tries")
    s.add_argument("--eval", type=int, default=40, help="number of feasible sets to assemble and score per degree")
    c = sub.add_parser("check")
    c.add_argument("dir")
    q = sub.add_parser("cues", help="LilyPond tab cues (participant + researcher) for a hand-built set")
    q.add_argument("dir")
    for f in ("png", "svg", "pdf"):
        q.add_argument("--" + f, action="store_true", help=f"also render {f} (needs lilypond)")
    q.add_argument("--no-fingers", action="store_true", dest="no_fingers", help="omit left-hand finger numbers")
    args = ap.parse_args(argv)
    {"counts": cmd_counts, "search": cmd_search, "check": cmd_check, "cues": cmd_cues}[args.cmd](args)


if __name__ == "__main__":
    main()
