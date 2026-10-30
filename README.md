# Controlled ukulele stimuli: pipeline v2 (build spec v1.3)

Python 3, needs numpy, scipy, matplotlib (mido only for tests). `legacy/` holds the retired random pipeline.

## Run
    python main.py counts                 # Tier 1: counts of chunks, chunk orders, valid bases per degree
    python main.py search                 # Tier 2: exhaustive search for complete prototype sets, best set -> output/prototype_degree2/
    python main.py search --degree 3      # one degree only
    python main.py check DIR              # validate a hand-built set (DIR/chunks.csv + DIR/items.csv)
    python tests.py                       # validators accept a valid set, reject broken items; MIDI round trip

## Modules
config.py (all parameters) | fretboard.py (positions, fingers) | chunks.py (chunk rules, junction cue) |
versions.py (motor boundaries, degree, neutrality, motor chunk IDs) | items.py (items, alternate, shift, probes) |
validators.py (checks 1-6) | feasibility.py (counts, search, family assembly) | rdm.py (separability report) |
difficulty.py (draft metric) | tables.py (note/item tables) | export.py (tab + MIDI) | loader.py (CSV in/out)

## Hand-built input (CSV, e.g. output/prototype_degree2/input/)
chunks.csv: chunk_id, fingering ("C0 C2 E0", optional "/finger"), alt_fingering, role (trained|new)
items.csv:  item_id, family_id, layer, variant_type (base|recombined|mixed|new-chunk), chunks (IDs, space separated),
            composition (misaligned motor chunks, e.g. 3-2-2-3-2), preserved
Alternate fingerings, string-pair shifts and probes are generated from the bases.

## Outputs per set (output/<set>/)
report.txt (checks, difficulty, RDM correlations), rdm_correlations.png, note_table.csv, item_table.csv,
stimuli/<item>.txt (tab with fingers and chunk markers) and .mid (90 bpm), stimuli/all_tabs.txt

## Implementation choices not fixed by the spec (see claude/implementation-questions.md)
- Motor chunk identity = content (string, fret, finger of its notes); "same chunk" = same content.
- A base uses 4 distinct musical chunks (ALLOW_CHUNK_REPEAT_IN_ITEM = False).
- "No repeated notes inside chunks" = no consecutive repeat; C-D-C is allowed.
- Musical chunk IDs outside the trained inventory are written "new:<pitches>".
- Recurrence check: each trained chunk in >= 2 bases; each misaligned base shares >= 1 motor chunk (same content) with another base.
- RDMs: cosine distance on unit-count vectors; identity models 0/1; Spearman over item pairs of all played items.
- Difficulty z-scores use a random sample of 1500 valid bases at the configured degree as reference.
- Accent probe: loud on the first note of each motor chunk of the base's misaligned composition.


## Tab cues (LilyPond, draft)

    python main.py cues DIR [--png] [--svg] [--pdf] [--no-fingers]
    python main.py search / check DIR      # also write the .ly sources to <output>/cues/

`cues.py` writes, per played item, `participant/<id>.ly` (tab staff only: fret digits on the right strings, left-hand
finger row underneath, no bar lines, time signature or chunk labels, 12 equally spaced columns) and
`researcher/<id>.ly` (notation + tab, musical chunk bars and IDs, finger row, aligned and misaligned motor-chunk rows).
Rendering needs LilyPond (`pip install lilypond` ships a binary). Known gaps: claude/tab-rendering-options.md, section 6.
