"""
progression_features.py
=============================

"""

from typing import Dict, Optional, Sequence, Set
from ukulele_geometry import DEFAULT_SCALE_LENGTH_MM
from music_theory import best_key_fit, major_scale_pcs
from chord_vocab import CHORD_VOCAB
from chord_difficulty import chord_difficulty, chord_transition_distance
from harmonic_distance import minimal_voice_leading_distance, common_tone_ratio, root_motion_fifths


def progression_features(
    chord_ids: Sequence[str],
    vocab: Dict[str, Dict] = None,
    scale_length_mm: float = DEFAULT_SCALE_LENGTH_MM,
    key_pcs: Optional[Set[int]] = None,
) -> Dict[str, float]:
    """Aggregates single-chord and transition difficulty (physical) plus harmonic
    features of a chord progression into one flat feature dict.

    chord_ids: variant IDs from the vocab, e.g. ['C (Var. 1)', 'Am (Var. 2)', ...].
    key_pcs: pitch classes of a fixed key. If None, the best fitting of all
    12 major keys is used, so `out_of_key_ratio` is always present."""
    vocab = vocab or CHORD_VOCAB
    missing = [c for c in chord_ids if vocab.get(c, {}).get("shape") is None]
    if missing:
        raise ValueError(f"Keine Griffposition bekannt fuer: {missing}")

    shapes = [vocab[c]["shape"] for c in chord_ids]
    pcs_list = [vocab[c]["pitch_classes"] for c in chord_ids]
    roots = [vocab[c]["root_pc"] for c in chord_ids]
    labels = [vocab[c]["label"] for c in chord_ids]

    chord_scores = [chord_difficulty(s, scale_length_mm) for s in shapes]
    transitions = [chord_transition_distance(shapes[i], shapes[i + 1], scale_length_mm)
                   for i in range(len(shapes) - 1)]
    harmonic = [minimal_voice_leading_distance(pcs_list[i], pcs_list[i + 1])
                for i in range(len(pcs_list) - 1)]
    common = [common_tone_ratio(pcs_list[i], pcs_list[i + 1]) for i in range(len(pcs_list) - 1)]
    root_moves = [root_motion_fifths(roots[i], roots[i + 1]) for i in range(len(roots) - 1)]

    if key_pcs is None:
        key_name, out_of_key = best_key_fit(pcs_list)
    else:
        out_of_key = sum(1 for p in pcs_list if not set(p) <= key_pcs) / len(pcs_list)

    n_chords = len(shapes)
    n_trans = max(len(transitions), 1)

    return dict(
        mean_chord_span_mm=sum(c.span_mm for c in chord_scores) / n_chords,
        max_chord_span_mm=max((c.span_mm for c in chord_scores), default=0.0),
        mean_fingers=sum(c.num_fingers for c in chord_scores) / n_chords,
        barre_count=sum(c.barre for c in chord_scores),
        mean_chord_difficulty_score=sum(c.score for c in chord_scores) / n_chords,
        mean_transition_physical_mm=sum(t.total_mm for t in transitions) / n_trans,
        max_transition_physical_mm=max((t.total_mm for t in transitions), default=0.0),
        barre_changes=sum(t.barre_change for t in transitions),
        total_physical_distance_mm=sum(t.total_mm for t in transitions),
        mean_minimal_voice_leading=sum(harmonic) / n_trans,
        max_minimal_voice_leading=max(harmonic, default=0.0),
        total_minimal_voice_leading=sum(harmonic),
        common_tone_ratio=sum(common) / n_trans,
        mean_root_motion_fifths=sum(root_moves) / n_trans,
        n_unique_chords=len(set(labels)),
        out_of_key_ratio=out_of_key,
    )