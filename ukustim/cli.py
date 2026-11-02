"""
cli.py   (run as: python main.py <command>)
=============================
Commands
  counts                          Tier-1 feasibility counts per degree of misalignment
  search [--degree D] [--bases 3-6] [--budget S] [--trained N] [--exact]
                                  search for prototype sets with the separability score as objective (3-6 bases);
                                  --exact = exhaustive exact-cover triples (3 bases, 6 chunks) ranked by the same score
  check DIR                       validate a hand-built set (chunks.csv + items.csv) and report separability
  cues DIR [--png --svg --pdf]    LilyPond tab cues (participant / researcher) for a hand-built set
  transpositions [--degree D]     how many valid bases allow a played transposition to each key
All outputs go to config.OUTPUT_DIR.
"""

import argparse
import json
import os
from typing import List

from ukustim import config
from ukustim.analysis import difficulty as dif
from ukustim.analysis import separability as sep
from ukustim.analysis import variety
from ukustim.checks import validators as val
from ukustim.core.inventory import Inventory
from ukustim.family import transposition
from ukustim.formats import cues, loader, tables
from ukustim.formats.export import export_items
from ukustim.selection import counts as counts_mod
from ukustim.selection import exact_cover as ec
from ukustim.selection import objective_search as osearch
from ukustim.selection import reference
from ukustim.selection.assemble import assemble_family


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def report_set(items, reg, notes, outdir, inv=None, title=""):
    """Validate, score, write tables / tabs / MIDI / cues / separability report for a list of items."""
    os.makedirs(outdir, exist_ok=True)
    results = val.validate_set(items)
    lines = [title, val.summarize(results), ""]
    if notes:
        lines += ["Notes:"] + ["  " + n for n in notes] + [""]
    played = [i for i in items if i.played]
    inv = inv or Inventory()
    model = dif.DifficultyModel.fit(reference.reference_items(inv, 1500, deg=config.MISALIGNMENT_DEGREE))
    by_id = {i.item_id: i for i in items}
    lines.append("Difficulty (mean z-score over the reference sample of valid bases):")
    for i in played:
        s = model.score(i)
        gap = ""
        if i.variant_type in ("alternate fingering", "played transposition") and i.base_item_id in by_id:
            gap = f"   gap to base {s - model.score(by_id[i.base_item_id]):+.2f}"
        lines.append(f"  {i.item_id:<10} {i.variant_type:<22} {s:+.2f}{gap}")
    rep = sep.report(items)
    lines += ["", variety.format_variety(variety.variety_report(items)), "", sep.format_report(rep)]
    _write(os.path.join(outdir, "report.txt"), "\n".join(lines) + "\n")
    sep.save_heatmap(rep, os.path.join(outdir, "rdm_correlations.png"))
    tables.write_tables(items, outdir)
    export_items(items, os.path.join(outdir, "stimuli"))
    cues.export_cues(items, os.path.join(outdir, "cues"))      # .ly sources; `main.py cues DIR --png` renders them
    return results, rep


def cmd_counts(args):
    inv = Inventory()
    rep = counts_mod.count_report(inv)
    _write(os.path.join(config.OUTPUT_DIR, "feasibility_counts.json"), json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def _parse_range(s: str) -> List[int]:
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def cmd_search(args):
    inv = Inventory()
    degrees = [args.degree] if args.degree else [1, 2, 3]
    lines = [f"Set search, strict chunk rule: turning points {config.TURNING_POINT_CHUNKS}; "
             f"{len(inv.chunks)} chunks; {args.trained} trained chunks."]
    summary, results = {}, []

    def log(s):
        print(s)
        lines.append(s)

    for d in degrees:
        if args.exact:
            sols, stats = ec.find_sets_exhaustive(inv, d, max_tries=args.max_tries, want=args.eval)
            evs = [osearch.evaluate(inv, s, alt_combos=400, seed=k) for k, s in enumerate(sols)]
            evs.sort(key=lambda e: e.score)
            summary[f"{d}/exact"] = dict(stats=stats, best_objective=evs[0].objective if evs else None)
            log(f"degree {d}, exact triples: {stats}; best objective {summary[f'{d}/exact']['best_objective']}")
            results += [(d, 3, e) for e in evs[:1]]
            continue
        for k in _parse_range(args.bases):
            ranked, stats = osearch.search(inv, d, k, n_trained=args.trained, budget_s=args.budget, log=log)
            summary[f"{d}/{k}"] = stats
            if ranked:
                results.append((d, k, ranked[0]))
    _write(os.path.join(config.OUTPUT_DIR, "search_summary.txt"), "\n".join(lines) + "\n")
    _write(os.path.join(config.OUTPUT_DIR, "search_summary.json"), json.dumps(summary, indent=1, default=str))
    if not results:
        print("no complete set found")
        return
    at_default = [r for r in results if r[0] == config.MISALIGNMENT_DEGREE] or results
    d, k, ev = min(at_default, key=lambda r: r[2].score)
    outdir = os.path.join(config.OUTPUT_DIR, f"prototype_degree{d}")
    res, rep = report_set(ev.items, ev.registry, ev.notes, outdir, inv,
                          f"Prototype set found by search: degree {d}, {k} bases, objective {ev.objective:.2f}")
    loader.save_set(ev.items, ev.registry, os.path.join(outdir, "input"))
    print(f"best set (degree {d}, {k} bases) written to {outdir}; checks failed: {sum(not r.passed for r in res)}; "
          f"E1 max|r| {sep.score_e1(rep):.2f}, E2 max|r| {sep.score_e2(rep):.2f}")
    for n in ev.notes:
        print("  note:", n)


def cmd_check(args):
    items, reg, notes = loader.load_set(args.dir)
    outdir = os.path.join(config.OUTPUT_DIR, "check_" + os.path.basename(os.path.normpath(args.dir)))
    results, rep = report_set(items, reg, notes, outdir, title=f"Hand-built set {args.dir}")
    print(val.summarize(results))
    print(sep.format_report(rep))


def cmd_cues(args):
    items, reg, notes = loader.load_set(args.dir)
    outdir = os.path.join(config.OUTPUT_DIR, "cues_" + os.path.basename(os.path.normpath(args.dir)))
    fmts = [f for f in ("png", "svg", "pdf") if getattr(args, f)]
    cues.export_cues(items, outdir, fmts, show_fingers=not args.no_fingers)
    print(f"cue sources{' and ' + '/'.join(fmts) if fmts else ''} written to {outdir}/participant and /researcher")


def cmd_transpositions(args):
    inv = Inventory()
    degrees = [args.degree] if args.degree else [1, 2, 3]
    out = {}
    for d in degrees:
        rep = transposition.feasibility_by_key(inv, d)
        out[d] = rep
        print(f"degree {d}: valid bases that allow a played transposition to the key (of {next(iter(rep.values()))['valid_bases']})")
        for k, v in sorted(rep.items(), key=lambda kv: -kv[1]["feasible"]):
            print(f"  {k:<3} {v['feasible']:>5}  ({v['orders']} distinct chunk orders)")
    _write(os.path.join(config.OUTPUT_DIR, "transposition_feasibility.json"), json.dumps(out, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default=None, help=f"output folder (default {config.OUTPUT_DIR})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("counts")
    s = sub.add_parser("search")
    s.add_argument("--degree", type=int)
    s.add_argument("--bases", default=f"{config.N_BASES}-{config.N_BASES_MAX}", help="number of bases, e.g. 3-6 or 4")
    s.add_argument("--trained", type=int, default=config.N_TRAINED_CHUNKS)
    s.add_argument("--budget", type=float, default=config.SEARCH_BUDGET_S, help="seconds per degree and number of bases")
    s.add_argument("--exact", action="store_true", help="exhaustive exact-cover triples (3 bases, 6 chunks)")
    s.add_argument("--max-tries", type=int, default=config.SEARCH_TRIALS, dest="max_tries")
    s.add_argument("--eval", type=int, default=40, help="(--exact) feasible sets to build and score per degree")
    c = sub.add_parser("check")
    c.add_argument("dir")
    q = sub.add_parser("cues", help="LilyPond tab cues (participant + researcher) for a hand-built set")
    q.add_argument("dir")
    for f in ("png", "svg", "pdf"):
        q.add_argument("--" + f, action="store_true", help=f"also render {f} (needs lilypond)")
    q.add_argument("--no-fingers", action="store_true", dest="no_fingers", help="omit left-hand finger numbers")
    t = sub.add_parser("transpositions", help="feasibility of the played transposition per target key")
    t.add_argument("--degree", type=int)
    for sp in (s, c, q):
        sp.add_argument("--transposition-key", dest="transposition_key", default=None,
                        help=f"target key of the played transposition (default {config.TRANSPOSITION_KEY})")
    args = ap.parse_args(argv)
    if args.output:
        config.OUTPUT_DIR = args.output
    if getattr(args, "transposition_key", None):
        config.TRANSPOSITION_KEY = args.transposition_key
    {"counts": cmd_counts, "search": cmd_search, "check": cmd_check, "cues": cmd_cues,
     "transpositions": cmd_transpositions}[args.cmd](args)
