"""
difficulty.py
=============================
Draft difficulty metric (build spec section 10): physical features of the fingering path, z-scored against
a reference sample of valid items, then averaged. The prototype is a single band; for now the metric is used
to report base-alternate gaps. Position shifts are always 0 in first position and therefore omitted.
"""

import json
import math
import statistics
from typing import Dict, Optional, Sequence

from ukustim.core import versions as vs
from ukustim.core.fretboard import step_distance_mm
from ukustim.core.items import Item

FEATURES = ["string_crossings", "fret_span", "distinct_fingers", "mean_step_mm", "max_step_mm", "little_finger_uses"]


def difficulty_features(item: Item) -> Dict[str, float]:
    pos = item.positions
    if pos is None:
        raise ValueError("listen-only item has no fingering")
    steps = [step_distance_mm(a, b) for a, b in zip(pos, pos[1:])]
    fretted = [p.fret for p in pos if p.fret > 0]
    return dict(
        string_crossings=len(vs.string_crossings(pos)),
        fret_span=(max(fretted) - min(fretted)) if fretted else 0,
        distinct_fingers=len({p.finger for p in pos if p.finger > 0}),
        mean_step_mm=sum(steps) / len(steps),
        max_step_mm=max(steps),
        little_finger_uses=sum(1 for p in pos if p.finger == 4),
    )


class DifficultyModel:
    """z-score reference (mean, std per feature); score = mean z over FEATURES."""

    def __init__(self, stats: Dict[str, Sequence[float]]):
        self.stats = stats

    @classmethod
    def fit(cls, items: Sequence[Item]) -> "DifficultyModel":
        feats = [difficulty_features(i) for i in items]
        stats = {}
        for f in FEATURES:
            vals = [x[f] for x in feats]
            sd = statistics.pstdev(vals)
            stats[f] = (statistics.fmean(vals), sd if sd > 0 else 1.0)
        return cls(stats)

    def score(self, item: Item) -> float:
        x = difficulty_features(item)
        return statistics.fmean((x[f] - self.stats[f][0]) / self.stats[f][1] for f in FEATURES)

    def save(self, path: str) -> None:
        json.dump(self.stats, open(path, "w"), indent=1)

    @classmethod
    def load(cls, path: str) -> "DifficultyModel":
        return cls({k: tuple(v) for k, v in json.load(open(path)).items()})
