"""Build spec v1.7: C-VIII combination components, their collinearity report, the M-IV / A-IV descriptive
reports, the model -> research-question table."""

import numpy as np

from tests.helpers import config, expect, fixture, transposable_base

from ukustim.analysis import models as md
from ukustim.analysis import separability as sep
from ukustim.family.transposition import played_transposition


def run():
    fx = fixture()
    base, alt, shift = fx.base, fx.alt, fx.shift
    if alt and shift:
        R = md.model_rdms([base, alt, shift], md.COMBINATION_MODELS + ["movement_graded"])
        expect("C-VIII sound: alternate 0, shift > 0", R["comb_sound"][0, 1] == 0 and R["comb_sound"][0, 2] > 0)
        expect("C-VIII movement: shift 0, alternate > 0", R["comb_movement"][0, 2] == 0 and R["comb_movement"][0, 1] > 0)
        expect("C-VIII movement equals the graded movement model", np.allclose(R["comb_movement"], R["movement_graded"]))
        expect("C-VIII interaction >= max(sound, movement) everywhere",
               np.all(R["comb_interaction"] >= np.maximum(R["comb_sound"], R["comb_movement"]) - 1e-12))
        expect("C-VIII product form = 1 - s_sound * s_move",
               np.allclose(R["comb_interaction_product"], 1 - (1 - R["comb_sound"]) * (1 - R["comb_movement"])))
        expect("C-VIII structure: alternate 0 (same intervals)", R["comb_structure"][0, 1] == 0)
    b, reg = transposable_base("D")
    old = config.TRANSPOSITION_KEY
    config.TRANSPOSITION_KEY = "D"
    tr, _ = played_transposition(b, reg)
    config.TRANSPOSITION_KEY = old
    if tr:
        R = md.model_rdms([b, tr], ["comb_structure", "comb_sound"])
        expect("C-VIII structure: transposition 0, sound 1", R["comb_structure"][0, 1] == 0 and R["comb_sound"][0, 1] == 1)
    col = sep.collinearity([i for i in fx.items if i.variant_type in sep.E2_VARIANTS])
    expect("collinearity: multiple R in [0, 1] and VIF >= 1 for every component",
           all((np.isnan(v["R"]) or (0 <= v["R"] <= 1 and v["vif"] >= 1 - 1e-9)) for v in col["components"].values())
           and set(col["components"]) == set(md.C8_COMPONENTS))
    # VIF of a component that is a copy of another is infinite / R = 1
    cols = sep.collinearity([i for i in fx.items if i.variant_type in sep.E2_VARIANTS],
                            ["comb_movement", "movement_graded", "comb_sound"])
    expect("collinearity: an exact copy has R = 1", abs(cols["components"]["comb_movement"]["R"] - 1) < 1e-6)
    d = sep.descriptive_reports(fx.items)
    expect("M-IV: finger = fret under the default finger rule (r = 1)", abs(d["m4"][("finger", "fret")] - 1) < 1e-9)
    expect("A-IV reports run over listen-only items too", d["n_heard"] > d["n_played"])
    try:
        md.model_rdms(fx.items, ["motor_elements"], include_listen_only=True)
        ok = False
    except ValueError:
        ok = True
    expect("motor models refuse listen-only items", ok)
    old = config.E2_INCLUDES_C8
    config.E2_INCLUDES_C8 = True
    s1, s2 = sep.scores(fx.items)
    config.E2_INCLUDES_C8 = False
    s1b, s2b = sep.scores(fx.items)
    config.E2_INCLUDES_C8 = old
    expect("E2_INCLUDES_C8 can only raise the E2 score", s1 == s1b and s2 >= s2b)
    old = config.E2_INCLUDES_C8
    tags = {}
    for flag in (False, True):
        config.E2_INCLUDES_C8 = flag
        tags[flag] = (sep._c8_tag("c8"), sep._c8_tag("c8_product"))
    config.E2_INCLUDES_C8 = old
    expect("C-VIII report tags: main block report-only unless E2_INCLUDES_C8; product form always report-only",
           tags[False] == ("   (report only)", "   (report only)")
           and tags[True] == ("   (part of the E2 score)", "   (report only)"))
    txt = sep.format_report(sep.report(fx.items))
    expect("report shows C-VIII, the descriptive reports and the 8a table",
           "C-VIII components" in txt and "Reports without optimization" in txt and "research questions they serve" in txt)
