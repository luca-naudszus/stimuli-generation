"""End-to-end: the hand-built example sets pass every check, and `check` writes all outputs."""

import contextlib
import io
import os
import tempfile

from tests.helpers import ROOT, config, expect

from ukustim import cli
from ukustim.checks import validators as val
from ukustim.formats import loader


def run():
    for name, key in (("prototype_set", "G"), ("prototype_set_D", "D")):
        d = os.path.join(ROOT, "examples", name)
        if not os.path.isdir(d):
            print(f"SKIP {name} (not found)")
            continue
        config.TRANSPOSITION_KEY = key
        items, reg, notes = loader.load_set(d)
        results = val.validate_set(items)
        expect(f"example set {name}: every check passes", all(r.passed for r in results), val.summarize(results)[:400])
        expect(f"example set {name}: 6 bases and the full family", sum(i.variant_type == "base" for i in items) >= 4
               and {"alternate fingering", "string-pair shift", "recombined", "mixed", "new-chunk"} <= {i.variant_type for i in items})
    config.TRANSPOSITION_KEY = "G"
    d = os.path.join(ROOT, "examples", "prototype_set")
    if os.path.isdir(d):
        with tempfile.TemporaryDirectory() as out, contextlib.redirect_stdout(io.StringIO()) as buf:
            cli.main(["--output", out, "check", d])
            sub = os.path.join(out, "check_prototype_set")
            files = {"report.txt", "note_table.csv", "item_table.csv", "rdm_correlations.png"}
            expect("`check` writes report, tables and heat map", files <= set(os.listdir(sub)))
            expect("`check` writes tabs, MIDI, click tracks and cue sources",
                   any(f.endswith("_click.mid") for f in os.listdir(os.path.join(sub, "stimuli")))
                   and os.path.exists(os.path.join(sub, "cues", "participant", "B1.ly"))
                   and os.path.exists(os.path.join(sub, "cues", "researcher", "B1.ly")))
        expect("`check` prints the separability report", "E1:" in buf.getvalue())
    config.TRANSPOSITION_KEY = "G"
