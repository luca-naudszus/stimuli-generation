# chords/ (placeholder)

The chord strand is a later stage (build spec section 11, preliminary spec from Q6): 4/4, one chord per bar, 6 chords
per item, harmonic units of 2 chords as musical chunks, 2 or 3 chords as motor chunks, a change-cost analogue of the
neutrality rule. Nothing here is wired into the melody pipeline yet. `chord_difficulty.py` is the old chord difficulty
code (from `legacy/`); the chord vocabulary is in `legacy/chord_vocab.py`.

When chords are added: put them in this package (vocabulary, change cost, chord chunks), reuse `core/versions.py`
(motor boundaries), `analysis/separability.py` and `formats/` (add chord-level columns to the note table).
