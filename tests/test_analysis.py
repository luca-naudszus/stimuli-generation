"""Model RDMs and the separability report."""

import numpy as np

from tests.helpers import config, expect, fixture, transposable_base

from ukustim.analysis import models as md
from ukustim.analysis import separability as sep
from ukustim.family.transposition import played_transposition


def run():
    fx = fixture()
    items = fx.items
    base, alt, shift = fx.base, fx.alt, fx.shift
    pl = [base, alt, shift] if alt and shift else [base]
    R = md.model_rdms(pl)
    if alt and shift:
        expect("concrete sound: alternate fingering = same sound as its base", R["concrete_sound"][0, 1] == 0 and R["concrete_sound"][0, 2] == 1)
        expect("movement identity: string-pair shift = same movement as its base", R["movement_identity"][0, 2] == 0 and R["movement_identity"][0, 1] == 1)
        expect("lh motor chunks: the shift shares them, the full definition does not",
               R["motor_chunk_misal_lh"][0, 2] < 1e-9 and R["motor_chunk_misal_full"][0, 2] > 0.99)
        expect("graded movement: shift 0, alternate in between",
               R["movement_graded"][0, 2] < 1e-9 and 0 < R["movement_graded"][0, 1] < 1)
        expect("abstract structure: alternate = same, shift = different", R["abstract_structure"][0, 1] == 0 and R["abstract_structure"][0, 2] == 1)
    expect("every RDM is symmetric with a zero diagonal", all(np.allclose(M, M.T) and np.allclose(M.diagonal(), 0) for k, M in md.model_rdms(items).items()
                                                               if k != "motor_chunk_crossing_lh"))
    # played transposition: same abstract structure, different sound and movement
    b, reg = transposable_base("D")
    old = config.TRANSPOSITION_KEY
    config.TRANSPOSITION_KEY = "D"
    tr, why = played_transposition(b, reg)
    config.TRANSPOSITION_KEY = old
    if tr:
        R = md.model_rdms([b, tr])
        expect("transposition: abstract structure shared, sound and movement differ",
               R["abstract_structure"][0, 1] == 0 and R["concrete_sound"][0, 1] == 1 and R["movement_identity"][0, 1] == 1)
        expect("transposition: scale degrees shared (relative to each key)", R["scale_degree"][0, 1] < 1e-9)
    # report structure
    rep = sep.report(items)
    expect("report has E1, E2 and nuisance parts", {"e1", "e2", "nuisance", "corr", "all"} <= set(rep))
    e1_variants = {i.variant_type for i in items if i.item_id in rep["e1"]["items"]}
    expect("E1 excludes shifts and probes, E2 holds family members",
           not e1_variants & {"string-pair shift", "played transposition"} and "string-pair shift" in {i.variant_type for i in items if i.item_id in rep["e2"]["items"]})
    expect("objective is a number in [0, 1.3]", 0 <= sep.objective(items) <= 1.3)
    expect("report text renders", "E1:" in sep.format_report(rep) and "Nuisance" in sep.format_report(rep))
    expect("undefined correlation counts as 1 in the score", sep._worst({("a", "b"): float("nan")}, [("a", "b")]) == 1.0)
