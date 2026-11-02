# Controlled ukulele stimuli: pipeline v2 (build spec v1.6)

Python 3 with numpy, scipy, matplotlib and Pillow (mido and LilyPond only for tests and cue images).
`legacy/` holds the retired random pipeline. Rationale and design live in the shared project docs
(`build-spec.md`, `stimulus-set-checklist.md`); this folder only implements them.

## Folder structure

```
main.py                    entry point (python main.py <command>)
ukustim/                   the package
  config.py                every parameter (key, thresholds, degree, metre, search budget, transposition key ...)
  cli.py                   commands and the per-set report
  core/                    what an item is
    music_theory.py  ukulele_geometry.py  fretboard.py   notes, strings, frets, fingers, relative string pattern
    chunks.py        keys.py                              chunk rules, junction (boundary) cue, scale degrees, transposition offsets
    versions.py                                           motor boundaries, degree of misalignment, neutrality rule, motor chunk IDs
    fingering.py     inventory.py                         neutral-fingering search; the chunk inventory and junction graph
    items.py                                              Item, ChunkDef, builders
  family/                  how family members are built from a base
    alternate.py  string_shift.py  transposition.py  probes.py
    generalization.py  (recombined: musical-only / motor-only / both, mixed, new-chunk)
    trained.py             what counts as trained; the proportions of the item table
  checks/validators.py     build spec checks 1-8
  selection/               choosing a set
    counts.py              feasibility counts per degree
    exact_cover.py         exhaustive triples (3 bases, 6 chunks)
    objective_search.py    3-6 bases, separability score as objective
    assemble.py            solution -> full item list
    solution.py  reference.py
  analysis/                is the set analysable?
    models.py  separability.py   model RDMs, E1 / E2 / nuisance correlations, objective
    difficulty.py                draft difficulty metric
  formats/                 files going out and coming in
    loader.py  tables.py  tab.py  midi.py  export.py  cues.py
  chords/                  placeholder for the chord strand (not wired; build spec section 11)
tests/                     python tests/run_all.py
examples/                  hand-built input sets and sample cue images
output/                    generated (not versioned)
```

## Run

    python main.py counts                           # feasibility counts per degree (strict chunk rule)
    python main.py search                           # 3-6 bases, degrees 1-3, objective-driven; best set at the default degree -> output/prototype_degree2/
    python main.py search --degree 2 --bases 4-6 --budget 60 --transposition-key D
    python main.py search --exact                   # exhaustive exact-cover triples (3 bases, 6 chunks), ranked by the same score
    python main.py check examples/prototype_set     # validate a hand-built set and report separability
    python main.py cues examples/prototype_set --png --svg
    python main.py transpositions                   # how many valid bases allow a played transposition per key
    python tests/run_all.py
    python main.py --output DIR ...                 # write somewhere else than output/

## What the search does

Valid bases (chunk order x misaligned composition x fingering, neutrality and 3-string span hold) are enumerated
(about 2,000 at degree 2). A set = K bases (3-6) whose shared chunks have the same fingering, every trained chunk in
at least 2 bases, minimum recurrence. Each candidate set is expanded to its full family and scored: the worst |r|
over the pairs that must separate (E1: musical chunk vs misaligned motor chunk, motor chunk vs concrete sound, vs
graded movement; E2 as a smaller term: movement / concrete sound / abstract structure), plus penalties for family
members that cannot be built. Random sampling, then local moves (replace one base). Time-boxed, not a proof of
optimality.

## Hand-built input (CSV)

`chunks.csv`: chunk_id, fingering ("C0 C2 E0", optional "/finger"), alt_fingering, role (trained|new).
`items.csv`: item_id, family_id, layer, variant_type (base|recombined|mixed|new-chunk), chunks (IDs, space separated),
composition (e.g. 3-2-2-3-2), preserved (recombination type).
Alternate fingerings, string-pair shifts, played transpositions and probes are generated from the bases.

## Outputs per set (output/<set>/)

`report.txt` (checks, difficulty, separability E1 / E2 / nuisance), `rdm_correlations.png`, `note_table.csv`,
`item_table.csv` (with key, trained proportions, recombination type), `stimuli/<item>.txt` (tab), `.mid` (90 bpm, 3/4) and
`_click.mid` (accent on beat 1), `cues/participant/<item>.ly` and `cues/researcher/<item>.ly`.

## Tab cues (LilyPond)

Participant cue: tab staff only, fret digits, left-hand finger row (0 = open string), no bar lines, time signature or
chunk labels, equal spacing, **fixed canvas** (the page is the canvas; never cropped). Researcher cue: notation + tab in
3/4 (one chunk per bar), chunk IDs (* = not trained), finger row, aligned / misaligned motor-chunk rows, key signature.
Missing: see claude/tab-rendering-options.md, section 6.

## Implementation choices not fixed by the spec (see claude/implementation-questions.md)

- Motor chunk identity: `full` = string, fret, finger; `lh` = fret, finger, relative string pattern (Q7, Q8). Recurrence uses `full`.
- A base uses 4 distinct musical chunks (ALLOW_CHUNK_REPEAT_IN_ITEM = False).
- Chunk IDs outside the trained inventory are written `new:<pitches>`; transposed chunks `new:<key>:<pitches>`.
- Motor-only recombined item: at least `MOTOR_ONLY_MIN_NEW_MUSICAL` (default 1) of its 4 musical chunks are new; the
  recombination type is always derived from the trained proportions.
- Played transposition: the smallest shift that keeps first position and a neutral fingering; the fingering of a
  transposed chunk is stored once and reused.
- RDMs: cosine distance on unit-count vectors; identity models 0/1; Spearman over item pairs. A constant or undefined
  model counts as |r| = 1 in the score (no evidence of separability).
- Difficulty z-scores use a random sample of 1500 valid bases at the configured degree as reference.
- Accent probe: loud on the first note of each motor chunk of the base's misaligned composition.
