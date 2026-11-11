# Pipeline v2 walkthrough: one base from start to finish

**Version 4 (11 Nov 2026).** Step 7 explains composition, registry and trained proportions. Version 3 (6 Nov 2026): section 3 rewritten: the full flow of `core/versions.py`, every function with its callers, and the motor-chunk identities. Version 2 (5 Nov 2026) was updated for build spec v1.7: the alternate tie-break is fixed (7a), and step 9 now covers the C-VIII combination components and the M-IV / A-IV reports. The assignment template is added to step 11. Maintained by the implementation chat. This explains what `pipeline_v2` does at each step, which file does it, and why. Every number comes from a real run on base **B1** of `examples/prototype_set` (strict chunk rule, degree 2, transposition key G). You can reproduce all of them with `python docs/walkthrough_trace.py` from the pipeline folder. Rationale for the design itself lives in the build spec and the checklist; this doc only covers how the code implements it.

## 0. The big picture

```
config.py ─► 1 neck ─► 2 chunks + junction graph ─► 3 two chunkings ─► 4 fingering search
                                                                             │
                     5 every valid base ("candidates", about 2,000) ◄────────┘
                                     │
        6 set search: sample K bases ─► 7 build the whole family ─► 9 score separability ─► keep / improve
                                     │
            best set ─► 8 checks ─► 9 separability report ─► 10 difficulty, variety ─► 11 files out
```

There are two ways in:

- **`python main.py search`** generates sets (steps 1 to 11).
- **`python main.py check DIR`** reads a set from `chunks.csv` and `items.csv`, rebuilds the generated family members from the bases, and runs steps 7 to 11. The search also writes its best set as those two CSVs, so you can edit a found set by hand and check it again.

Every parameter is in `ukustim/config.py`. Modules read it when a function runs, not at import, so a script or test can set `config.MISALIGNMENT_DEGREE = 3` and every later call follows.

---

## 1. The neck: which notes can be played, and where

**Files:** `core/ukulele_geometry.py`, `core/music_theory.py`, `core/fretboard.py`.

A note on the neck is a `Pos(string, fret, finger)`. Strings are ordered **G, C, E, A** (physical order on the neck). The open pitches are G4 = 67, C4 = 60, E4 = 64, A4 = 69, so the G string is the high re-entrant one. The finger follows `FINGER_RULE = "fret"`: fret 1 uses finger 1, …, fret 4 uses finger 4, and an open string is 0. One finger per fret is the only fingering model in first position.

`available_pitches()` takes every pitch reachable on frets 0 to 4 and keeps the ones in C major:

> C4 D4 E4 F4 G4 A4 B4 C5 (8 pitches)

`positions_for_pitch()` lists where each pitch can be played, lowest fret first. Only four of the eight pitches have a second place:

| Pitch | Positions | | Pitch | Positions |
|---|---|---|---|---|
| C4 | C0 | | G4 | **G0, E3** |
| D4 | C2 | | A4 | **A0, G2** |
| E4 | **E0, C4** | | B4 | **G4, A2** |
| F4 | E1 | | C5 | A3 |

That table explains a lot later. Alternate fingerings can only move E4, G4, A4 and B4, and a chunk usually has only 2 or 4 fingerings.

`relative_string_pattern()` gives the string change between consecutive notes (0 = same string, +1 = one string towards A). It is part of the "same movement" definition (Q8).

## 2. Musical chunks and the boundary cue

**File:** `core/chunks.py` (wrapped by `core/inventory.py`).

**Enumerate.** `enumerate_chunks()` tries all 8³ = 512 three-note sequences over those pitches. `within_chunk_problems()` rejects one if:

- it has a turning point (direction change inside the chunk), while `TURNING_POINT_CHUNKS = "forbid"`;
- it has a repeated note;
- it has an interval of 3 semitones or more (that would compete with the leap cue).

Examples of rejections: C4-D4-C4 (turning point), C4-E4-G4 (intervals 4 and 3), C4-D4-D4 (repeat).

What survives is **12 chunks**: the six rising stepwise runs (C-D-E, D-E-F, E-F-G, F-G-A, G-A-B, A-B-C) and their six reversals.

**Junction cue.** `junction_cues(a, b)` looks at the interval `b` from the last note of chunk A to the first note of chunk B:

- **leap:** 3 ≤ |b| ≤ 7, and |b| is larger than every interval inside A and inside B;
- **direction:** the sign of `b` differs from A's last interval, and both chunks are monotonic. Under the strict rule they always are.

A boundary needs at least one cue. A repeated note (`b = 0`) or a jump over 7 has none.

| A, B | cue |
|---|---|
| C-D-E, D-E-F | direction (E down to D) |
| C-D-E, G-A-B | leap (E up to G, 3 semitones) |
| E-D-C, G-A-B | leap + direction |
| C-D-E, E-F-G | none (E repeated) |

**Junction graph.** `junction_graph()` stores, for each chunk, the chunks that may follow it: 80 edges in total. For example, C-D-E may be followed by D-E-F, G-F-E, G-A-B, A-G-F, A-B-C and B-A-G.

**Chunk orders.** `enumerate_chunk_tuples()` is a depth-first walk through the graph. It collects every path of 4 distinct chunks (distinct because `ALLOW_CHUNK_REPEAT_IN_ITEM = False`): **2,476 orders**.

B1's order is **C-D-E | D-E-F | E-F-G | F-G-A**: three direction cues, each a step back of 1 or 2 semitones.

## 3. The two chunkings and the neutrality rule

**File:** `core/versions.py`. This module knows nothing about pitches. It deals with **where boundaries lie** in a 12-note item and answers four questions for the rest of the pipeline:

- **(a)** Which motor groupings exist?
- **(b)** Where are their boundaries, and how misaligned are they with the musical chunks?
- **(c)** Does a fingering favour one grouping over the other? (This is the neutrality rule.)
- **(d)** What are the motor chunks of an item, and what is their identity?

**3.1 The picture to keep in mind.** Here is base B1 with everything this module computes:

```
note (0-based)    0     1     2     3     4     5     6     7     8     9     10    11
B1                C0    C2    C4    C2    E0    E1    E0    E1    E3    E1    E3    G2
transition t         1     2     3     4     5     6     7     8     9    10    11
musical M                        |                 |                 |
motor B (3-2-3-2-2)              |           |                 |           |
M Δ B (forbidden)                            x     x           x     x     x
string change                          ^                                         ^
```

**Indexing.** Notes are 0-based (Python lists); transitions are 1-based. Transition *t* lies between note *t* − 1 and note *t*, so transition 3 is the gap after the third note.

A composition (a tuple of motor-chunk lengths, e.g. `(3, 2, 3, 2, 2)`) describes the misaligned motor chunking. The aligned chunking is always `(3, 3, 3, 3)`.

**3.2 The flow.** Functions in the order the pipeline uses them:

```
compositions()                         all ways to cut 12 notes into 2s and 3s (12 compositions)
   └─ misaligned_compositions(d)       keep those with degree d (5 at degree 2)
         uses boundaries(), degree(), musical_boundaries()
                    │
   for every chunk order × composition (step 5)
                    │
   forbidden_crossings(comp) = M Δ B   ──►  fingering search (core/fingering.py, step 4)
                    │                       rejects any option with a string change in M Δ B
   neutrality_violations(positions, comp)   = string_crossings(positions) ∩ M Δ B
                    │                       used to test candidate alternate fingerings and by check 2
   a valid base exists
                    │
   motor_chunks(positions, comp, mode)      cut the item into motor chunks and name each one
      = segments(comp) + motor_id(...)
                    │
   crossing_motor_ids(positions, comp)      the motor chunks that span a musical boundary (is_crossing)
                    │
   used by: recurrence (search, check 4), trained proportions, model RDMs, note table, variety report
```

**3.3 Every function, with B1's values and its callers.**

| Function | What it returns | B1 | Called by |
|---|---|---|---|
| `musical_boundaries()` | M = transitions after each musical chunk | {3, 6, 9} | `degree`, `misaligned_compositions`, `forbidden_crossings`, `is_crossing`; check 2; the `musical_boundary` model |
| `compositions()` | every tuple of 2s and 3s summing to 12, by a recursive search like the one for chunk orders | 12 tuples, from 2-2-2-2-2-2 to 3-3-3-3 | only `misaligned_compositions` (and tests) |
| `aligned_composition()` | `(3, 3, 3, 3)` | | trained proportions (aligned motor chunks), note table, `motor_chunk_aligned_*` models, the aligned row of tabs and cues; probes when an item has no composition |
| `boundaries(comp)` | B = running sums of the composition, without the last one (12) | 3, 3+2, 3+2+3, … = {3, 5, 8, 10} | `degree`, `misaligned_compositions`, `forbidden_crossings`; check 2 (B ≠ M) |
| `degree(comp)` | \|M − B\|: the musical boundaries that are not motor boundaries | {6, 9} → 2 | `misaligned_compositions`; the search's `feasible()` (every base has the chosen degree); the item table |
| `misaligned_compositions(d)` | compositions with B ≠ M and degree d | 5 at d = 2: 2-2-2-2-2-2, 2-2-3-2-3, 2-3-2-2-3, 3-2-2-3-2, 3-2-3-2-2 | every place that loops over compositions: `candidates`, `counts`, `exact_cover`, `reference`, `assemble`, transposition feasibility |
| `forbidden_crossings(comp)` | M Δ B (symmetric difference) | {5, 6, 8, 9, 10} | fingering search; `neutrality_violations`; the motor-only recombination search; check 2 |
| `string_crossings(positions)` | transitions where the string changes | {4, 11} | `neutrality_violations`; check 2; the difficulty metric (number of crossings) |
| `neutrality_violations(positions, comp)` | string crossings that fall in M Δ B (empty = neutral) | ∅ | `items.structurally_ok`, which tests each candidate alternate fingering; check 2. (Shifts keep the base's crossings; transpositions and recombined items are fingered with the search below, which applies M Δ B itself.) |
| `segments(comp)` | 0-based `[start, end)` ranges of the motor chunks | (0,3) (3,5) (5,8) (8,10) (10,12) | `motor_chunks`; the accent probe (the start of each segment is played loud); the motor-only recombination (cuts the bases into their motor-chunk pieces) |
| `is_crossing(start, end)` | True if a musical boundary lies strictly inside `[start, end)` | (5,8) and (8,10) | `crossing_motor_ids`; the crossing-chunk model |
| `motor_id(positions, mode)` | the name of one motor chunk (see 3.5) | `E1/1-E0/0-E1/1` | only `motor_chunks`; nothing else calls it directly |
| `motor_chunks(positions, comp, mode)` | list of (start, end, motor_id) for one chunking | five triples, see 3.5 | trained proportions, recurrence (search and check 4), motor-chunk models, note table, variety report |
| `crossing_motor_ids(positions, comp)` | the IDs of the crossing motor chunks (`full` mode) | {`E1/1-E0/0-E1/1`, `E3/3-E1/1`} | recurrence in the search (`exact_cover._share_ok`) and in check 4; variety report |
| `comp_to_str`, `comp_from_str` | `(3,2,3,2,2)` ↔ `"3-2-3-2-2"` | | CSV files, tables, reports |

**Why `start < t < end`.** A motor chunk `[a, b)` contains notes *a* to *b* − 1, so its internal transitions are *a* + 1 to *b* − 1. A boundary *t* therefore lies inside the chunk exactly when *a* < *t* < *b*. For example, `(3, 5)` is notes 3 and 4 with internal transition 4: no musical boundary, so not crossing. `(5, 8)` has internal transitions 6 and 7: it contains boundary 6, so it is crossing.

**Why the fingering search doesn't call `neutrality_violations`.** `neutrality_violations` needs all 12 positions. The fingering search (`valid_assignments`, step 4) builds a base chunk by chunk and wants to reject a bad option as soon as it is placed. So it applies the same test locally to each new chunk:

- a crossing inside the chunk at transition *t*₀ + *q* + 1, where *t*₀ is the transition just before the chunk and *q* the crossing's position inside it;
- the junction crossing at *t*₀ itself.

Both are checked against `forbidden_crossings(comp)`. The result is the same; the local version only prunes earlier.

**3.4 Why M Δ B.** Two facts:

1. A string change is a physical seam in the movement, so it is a natural place to break a sequence into units, whatever was trained.
2. The aligned and misaligned versions of a base use the **same notes and fingering**; they differ only in how the base is taught.

For a chunking effect to come from training, the physical layout must favour neither chunking. Every transition is one of four kinds:

| Kind | B1 transitions | A string change here… |
|---|---|---|
| boundary in both (M ∩ B) | 3 | marks a break that both chunkings have → neutral, allowed |
| boundary in neither | 1, 2, 4, 7, 11 | lies inside a chunk in both → neutral, allowed |
| musical boundary only (M − B) | 6, 9 | would hand the aligned grouping a physical boundary → forbidden |
| motor boundary only (B − M) | 5, 8, 10 | would hand the misaligned grouping a physical boundary → forbidden |

The two forbidden kinds together are M Δ B. B1 changes string at 4 and 11, both "neither", so it is neutral.

The cost is that the forbidden set grows with the degree: 3 transitions at degree 1, 5–6 at degree 2, 7 at degree 3. This is why valid bases drop from 1,216 to 524 to 107. It is also why the unshared boundaries rarely get a leap (Q15): a leap there would need a string change.

**3.5 Motor chunks and their identity.** `motor_chunks()` walks `segments(comp)` and names each slice with `motor_id()`. B1 in the misaligned version (3-2-3-2-2):

| Segment | Notes | `full` ID | `lh` ID | Crossing? |
|---|---|---|---|---|
| (0, 3) | C0 C2 C4 | `C0/0-C2/2-C4/4` | `0/0-2/2-4/4@+0,+0` | no |
| (3, 5) | C2 E0 | `C2/2-E0/0` | `2/2-0/0@+1` | no |
| (5, 8) | E1 E0 E1 | `E1/1-E0/0-E1/1` | `1/1-0/0-1/1@+0,+0` | yes (boundary 6) |
| (8, 10) | E3 E1 | `E3/3-E1/1` | `3/3-1/1@+0` | yes (boundary 9) |
| (10, 12) | E3 G2 | `E3/3-G2/2` | `3/3-2/2@-2` | no |

With `aligned_composition()` the same function gives B1's aligned motor chunks: `C0/0-C2/2-C4/4`, `C2/2-E0/0-E1/1`, `E0/0-E1/1-E3/3`, `E1/1-E3/3-G2/2`.

The two identities:

- **`full`** = string, fret and finger of each note. Two motor chunks are the same only if they are physically identical. This is the default, used for recurrence (search and check 4) and the trained proportions.
- **`lh`** (left hand) = fret and finger of each note, plus the relative string pattern after `@` (+1 = one string towards A, −2 = two strings towards G). The same hand shape on another string pair counts as the same chunk, so a string-pair shift shares its `lh` motor chunks with its base (Q7, Q8). Used by the `motor_chunk_*_lh` models, the crossing-chunk model and the `lh` columns of the note table.

A side effect of `lh`: C0-C2-C4 (C-D-E) and G0-G2-G4 (G-A-B) get the same `lh` ID. That is intended (same hand movement), but it means two items with different musical chunks can be identical on the `lh` motor model (step 9).

## 4. Fingering search for one chunk order

**Files:** `core/chunks.py` (`fingering_options`), `core/fingering.py` (`valid_assignments`).

**Options per chunk.** Each chunk gets every combination of its notes' positions. C-D-E has 2 options (E4 on E0 or C4), D-E-F has 2, E-F-G and F-G-A have 4 each. For example, E-F-G can be played as E0 E1 G0, E0 E1 E3, C4 E1 G0 or C4 E1 E3.

**The search.** For B1's order with 3-2-3-2-2 that makes 2·2·4·4 = **64 combinations**, of which **4 are valid**. `valid_assignments()` is a recursive search that adds one chunk at a time and prunes as soon as a rule breaks:

1. A string change inside the chunk must not land in F.
2. A string change at the junction with the previous chunk (previous chunk ends on another string than this one starts on) must not land in F.
3. The strings used so far must fit in 3 adjacent strings (`MAX_STRING_SPAN`).

Examples for B1's order:

- **Rejected:** C0 C2 E0 | C2 E0 E1 | E0 E1 **G0** | E1 **G0** A0. It crosses strings at 8, 9 and 10, which are all forbidden.
- **Valid (used in B1):** C0 C2 C4 | C2 E0 E1 | E0 E1 E3 | E1 E3 G2. It crosses only at 4 and 11.

The optional `fixed` argument pins the fingering of some chunks. That is how the rule "a chunk is fingered the same wherever it recurs" is enforced everywhere else.

## 5. Every valid base

**File:** `selection/objective_search.py` (`candidates`).

A valid base is a `Cand`: chunk order, misaligned composition and one valid fingering assignment. Steps 2 to 4 are run for every order and every composition of the chosen degree, keeping every valid assignment.

At degree 2: **1,950 candidates**, from 524 (order, composition) pairs that have at least one valid fingering. Degree 1 has 8,981 and degree 3 has 185.

Each candidate also gets a `transposable` flag: does a played transposition to `TRANSPOSITION_KEY` exist (step 7e)? Computing this once up front lets the sampler prefer such bases.

## 6. The set search

**File:** `selection/objective_search.py` (`search`, `sample_solution`, `feasible`, `evaluate`, `neighbours`). Called by `cli.cmd_search` for each degree and each number of bases K (3 to 6).

**6a. Sample a set** (`sample_solution`).

1. Pick a first base. 70 % of the time it comes from the transposable candidates.
2. Add bases one at a time from the candidates that are *compatible*:
   - a different chunk order;
   - the same fingering for every chunk already in the set;
   - the set still uses at most 6 chunks (`N_TRAINED_CHUNKS`).

   Each compatible candidate is drawn with weight (1 + 4·shared²) · (1 + 3·transposable). The weight favours bases that reuse chunks already in the set, which is what makes recurrence possible, and transposable bases.

**6b. Feasibility** (`feasible`):

- all orders distinct;
- every chunk in at least 2 bases;
- the turning-point cap holds;
- every composition has the right degree;
- every base is valid with the set's fingering;
- the **minimum recurrence** rule holds: each base has a crossing motor chunk (`full` identity) that also occurs in another base (`exact_cover._share_ok`).

**6c. Evaluate** (`evaluate`):

1. Build the set's whole family (step 7).
2. Compute E1 and E2 (step 9).
3. Combine them:

```
objective = E1 + 0.2 · E2
score     = objective + penalties − 0.01 · (number of distinct compositions)
```

The penalties apply to family members that could not be built:

- 0.15 per base without an alternate fingering;
- 0.15 per base without a string-pair shift;
- 0.1 × the share of bases without a transposition;
- 0.05 per missing generalization item.

These weights are my choice, not the spec's; they only rank sets. Lower score is better.

**6d. Time box.** The first 60 % of `SEARCH_BUDGET_S` is random sampling. The rest is local search: pick one of the 3 best sets, try up to 4 neighbours (replace one base with a compatible candidate), and keep whatever scores better.

**6e. Output.** The best set at the default degree is written by `report_set` (steps 8 to 11) and saved as CSVs (`loader.save_set`).

**Alternative:** `--exact` uses `selection/exact_cover.py`, which enumerates triples of orders covering 6 chunks exactly twice. It only handles 3 bases and gave a worse E1 (0.64).

## 7. Building the family of a set

**Files:** `selection/assemble.py` (`assemble_family`), `family/*`. For hand-built sets, `formats/loader.py` (`with_family_members`) calls the same builders.

Three terms used throughout this step:

- **Composition:** an item's misaligned motor chunking, as a tuple of chunk lengths (2s and 3s summing to 12), e.g. `(3, 2, 3, 2, 2)`. The aligned chunking is always 3-3-3-3 and is not stored.
  - Bases get theirs from the search.
  - Alternates, shifts, transpositions and probes inherit the base's composition.
  - Generalization items take the first composition of the set's degree that allows a neutral fingering.
- **Registry:** `Dict[chunk ID, ChunkDef]`, the one place that says how each chunk is played.
  - A `ChunkDef` holds the pitches, the fingering, at most one alternate, and a role (`trained`, `new` or `transposed`).
  - Items are built from chunk IDs through it (`build_item`), so a chunk can only be fingered one way.
  - It is saved as `chunks.csv`.
- **Trained:** occurs in a base of the set; see the end of this step.

**7a. Registry and alternate choice** (`_choose_alternates`). The registry maps chunk ID to `ChunkDef`, which holds the pitches, the main fingering and at most one alternate fingering (Q4).

Each chunk can take any of its other fingerings as its alternate, or none. Up to 400 random combinations are tried. For each, the code counts how many bases then get a valid alternate item and keeps the best combination. Ties go to the combination whose alternate items move **more** notes in total, as Q4 asks (fixed on 5 Nov; before, ties went to fewer moved notes). The example set was built before the fix, so its alternates may differ from what a new search would choose; it is still a valid set.

**7b. Base** (`core/items.build_item`). It concatenates the registry fingerings of its chunk IDs:

> **B1** = C0 C2 C4 | C2 E0 E1 | E0 E1 E3 | E1 E3 G2, composition 3-2-3-2-2

- Motor chunks (`full`): `C0-C2-C4`, `C2-E0`, `E1-E0-E1`, `E3-E1`, `E3-G2`.
- Crossing motor chunks: `E1-E0-E1` and `E3-E1` (they span boundaries 6 and 9).

**7c. Alternate fingering** (`family/alternate.py`).

1. Take the chunks of the base that have an alternate in the registry.
2. Try the largest subset first, and within a size the subset that moves the most notes.
3. Accept a subset if it uses at least 2 chunks, moves at least 2 notes, and still satisfies neutrality and the string span.

> **B1-alt** = C0 C2 **E0** | C2 E0 E1 | E0 E1 E3 | E1 E3 **A0**

Note 3 (E4) moves from C4 to E0, and note 12 (A4) moves from G2 to A0. The pitches are identical.

**7d. String-pair shift** (`family/string_shift.py`). Every note moves one string with the same fret and finger. "down" (towards G) is tried first, then "up". B1 uses the G string, so "down" is impossible; "up" maps C→E, E→A, G→C.

> **B1-shift** = E0 E2 E4 | E2 A0 A1 | A0 A1 A3 | A1 A3 C2

- The pitches are now E4 F#4 G#4 F#4 A4 A#4 A4 A#4 C5 A#4 C5 **D4**.
- The notes moved C→E rise 4 semitones and E→A rise 5, but the last note, moved from the high G string to the low C string, drops 7 (A4 to D4). The last step of the melody becomes a fall of 10 semitones (C5 to D4).
- Frets, fingers and the relative string pattern are unchanged (check 6). Its musical chunks are all `new:`.

**7e. Played transposition** (`family/transposition.py`). `keys.transposition_offsets()` lists the shifts that reach the target key and keep every pitch on frets 0 to 4. For G that is +7 or −5 (or ±12 more).

B1 spans C4 to A4. Shifted +7 it reaches E5, above the top note C#5. Shifted −5 it starts at G3, below C4. So B1 has no G transposition (note: "no shift to G keeps every pitch in first position"); this is Q11.

When a shift exists:

1. `valid_assignments()` searches the new pitches with the base's composition.
2. Among the valid fingerings, it takes the one with the lowest fret sum.
3. The transposed chunks are stored in the registry as `new:<key>:<pitches>`, so they are fingered identically in every transposed item.

**7f. Listen-only probes** (`family/probes.py`). These have no fingering (`positions = None`):

- **mode swap:** degrees 3, 6 and 7 are lowered: C D D# D D# F D# F G F G G#.
- **transposition:** +2 semitones, into D.
- **accent:** the same notes with velocity 115 on the first note of each misaligned motor chunk (notes 1, 4, 6, 9, 11) and 70 elsewhere. The accent grouping therefore crosses the musical chunks.

**7g. Generalization items** (`family/generalization.py`).

- **`recombined_musical`** looks for trained chunks in an order that no base uses, with every junction in the graph and the set's fingering fixed. It classifies each hit from the trained proportions and keeps the first `both` and the first `musical-only`.
- **`recombined_motor`** collects every misaligned motor-chunk segment of the bases. A depth-first search chains them to fill a composition. `partial_ok` prunes as it goes: neutrality, string span, chunk rules, junction cues, and a trained chunk must keep its registered fingering. The result with the most new musical chunks wins, as long as at least `MOTOR_ONLY_MIN_NEW_MUSICAL` = 1 is new.
- **`mixed_or_new`** finds an order with 2 trained and 2 new chunks (X1), or with 0 trained chunks (N1).
- **`register_new`** gives a new chunk the ID `new:<pitches>`. If the same pitches come up with a different fingering, the ID gets a suffix: X1 contains `new:G4-F4-E4~2` because N1 already registered G-F-E with another fingering.

**Trained proportions** (`family/trained.py`). `Trained(bases)` collects three sets from the bases:

- musical chunk IDs;
- `full` motor-chunk IDs, with each base cut by its own composition;
- `full` motor-chunk IDs, with each base cut 3-3-3-3.

For any item, `proportions()` gives the share of its musical chunks (out of 4), of its misaligned motor chunks (out of 5 or 6) and of its aligned motor chunks (out of 4) that are in those sets. Musical chunks match by ID, so `new:` never counts; motor chunks match by content. This is why the new-chunk item N1 still has 2 of 5 trained motor chunks.

The recombination type follows from the proportions:

- musical = 1 and motor = 1 gives **both**;
- only musical = 1 gives **musical-only**;
- only motor = 1 gives **motor-only**.

In `recombined_musical` every chunk is trained by construction, so the misaligned motor proportion alone decides between both and musical-only. R-musical has 4 of 5 trained motor chunks, because its `G0-G2-G4` (all of G-A-B) never occurs in a base under a composition that starts with 3. "Trained" currently counts bases only, not trained variants (Q18).

| Item | musical | motor, misaligned | motor, aligned | type |
|---|---|---|---|---|
| B1-alt | 1.00 | 0.80 | 0.50 | |
| B1-shift | 0 | 0 | 0 | |
| R-both | 1.00 | 1.00 | 1.00 | both |
| R-musical | 1.00 | 0.80 | 1.00 | musical-only |
| R-motor | 0.75 | 1.00 | 0.75 | motor-only (1 of 4 chunks new, Q12) |
| X1 | 0.50 | 0.67 | 0.50 | |
| N1 | 0 | 0.40 | 0 | |

## 8. Checks

**File:** `checks/validators.py`. Every check returns a `Result`, whether it passed or failed, so the report shows what was tested. The checks are written independently of the builders, so a bug in a builder shows up here.

| Check | What it tests |
|---|---|
| S | 12 notes, 4 chunks; the composition uses 2s and 3s and sums to 12 |
| 1 | frets 0 to 4; positions give the stated pitches; at most 3 adjacent strings; finger 0 exactly on open strings |
| 2 | composition differs from aligned; string crossings avoid M Δ B |
| 3 | each chunk clean; a cue at every musical boundary (skipped for shifts and probes) |
| 4 (set) | every trained chunk in at least 2 bases; turning-point share; same fingering wherever a chunk recurs; one alternate per chunk; minimum recurrence |
| 5 | alternate: same pitches, at least 2 notes in at least 2 chunks moved, only notes with a second position, same chunk IDs and composition |
| 6 | shift: same frets, fingers and relative string pattern; one common string step; pitches follow from the strings |
| 7 | transposition: intervals kept, new key, every pitch in it, base composition, different pitches |
| 8 | every chunk starts on beat 1 in 3/4 |

## 9. Separability

**Files:** `analysis/models.py`, `analysis/separability.py`.

**Model RDMs.** Each model turns an item into something comparable:

- **Count models** (`count_units`) give a bag of units per item: musical chunk IDs, misaligned motor chunks in `full` or `lh` form, pitches, intervals, and so on. The bag becomes a vector, which is normalized to length 1; distance = 1 − cosine.
- **Identity models** give 0 if two items are the same (pitch sequence, interval sequence or movement) and 1 otherwise.
- **`movement_graded`** gives 1 − the share of positions with the same (fret, finger, string step).

Four E1 items as an example:

```
musical_chunk          B1   B1-alt  B2   R-musical      motor_chunk_misal_lh   B1   B1-alt  B2   R-musical
B1                     0    0       .25  .50            B1                     0    .40     .80  .80
B1-alt                 0    0       .25  .50            B1-alt                 .40  0       .80  .80
B2                     .25  .25     0    .25            B2                     .80  .80     0    0
R-musical              .50  .50     .25  0              R-musical              .80  .80     0    0
```

The two models disagree in the right way. B1 and B1-alt share all musical chunks but not all motor chunks. Note that B2 and R-musical have identical `lh` motor chunks, because `lh` treats C0-C2-C4 and G0-G2-G4 as the same movement.

**Correlation.** `pair_correlations` takes the upper triangle of two RDMs and computes Spearman's r. If either model is constant, r is undefined (NaN), and the score counts it as |r| = 1: a constant model gives no evidence of separability.

**Evaluation sets.**

- **E1** = bases, alternates and generalization items: 17 items, 136 pairs.
- **E2** = bases, alternates, shifts and transpositions: 18 items here.

Results for this set:

| E1 pair (must separate) | r |
|---|---|
| musical chunk vs motor chunk, misaligned, full | 0.25 |
| musical chunk vs motor chunk, misaligned, lh | 0.23 |
| motor chunk lh vs concrete sound | **0.26** (worst, so E1 = 0.26) |
| motor chunk lh vs movement graded | 0.21 |

In E2, concrete sound vs abstract structure is r = **1.0**, so E2 = 1.0. Without a played transposition, no two items share intervals while differing in pitches: a shift changes both. That is Q11 in numbers.

The report also lists analysis contrasts, such as aligned motor chunks and crossing motor chunks, and the nuisance models (Q14). It draws the full model-by-model matrix as `rdm_correlations.png`.

**C-VIII combination components (build spec v1.7).** Three graded similarities between items *i* and *j*:

- `s_sound`: the share of the 12 positions with the same pitch;
- `s_move`: the share with the same (fret, finger, string step);
- `s_struct`: the share of the 11 intervals that match.

The components are distances:

- sound = 1 − s_sound;
- movement = 1 − s_move (identical to `movement_graded`);
- structure = 1 − s_struct;
- interaction = 1 − the share of positions where pitch **and** movement match;
- the alternative interaction 1 − s_sound × s_move, which is reported too.

`separability.collinearity` takes the E2 items, ranks the upper-triangle values, regresses each component on the others, and reports the multiple R and VIF (target R < 0.3, i.e., VIF < 1.10).

For this set the components are far from that target: R = 0.88 for sound and interaction, 0.78 for movement and structure. In first position the same pitch nearly always means the same position, so sound and interaction differ only at the notes an alternate moves. This is Q16; the result is reported, not enforced (`E2_INCLUDES_C8 = False`).

**Reports without optimization (v1.7).** These are descriptive only:

- **M-IV**, over the played items: r(finger, fret) = 1.00, because the finger is the fret number; r(string, absolute pitch) = 0.87.
- **A-IV**, over all heard items, listen-only probes included, since auditory models need no fingering:
  - r(absolute pitch, scale degree) = 0.82;
  - r(interval size, musical boundary) = 0.17 (definition in Q17);
  - the concrete / relational / tonal split;
  - the variance of the interval and contour RDMs (the contour RDM has only 7 distinct distances).

The report ends with the section 8a table: each model, the research questions it serves, and what it must separate from.

## 10. Difficulty and variety

**Files:** `analysis/difficulty.py`, `analysis/variety.py`, `selection/reference.py`.

**Difficulty.** Six features of the fingering path: string crossings, fret span, distinct fingers, mean and maximum step distance in mm on a soprano neck, and little-finger uses.

- Each feature is z-scored against 1,500 random valid bases (`reference_items`); the score is the mean z.
- The report prints each played item's score and the gap between each alternate or transposition and its base. Bands are not used yet (Q5).

**Variety.** The variety report counts the compositions of the bases, the positions (1 to 4) at which each chunk appears, and how many motor chunks and crossing motor chunks recur (Q7, step 3). The search uses only the composition count, as the small bonus in 6c.

## 11. Files out

**Files:** `cli.report_set`, `formats/*`. Everything goes to `output/<set>/`:

- `report.txt`: checks, notes on what could not be built, difficulty, variety, separability.
- `rdm_correlations.png`: the full model-by-model correlation matrix.
- `note_table.csv` (one row per note) and `item_table.csv` (one row per item, with key, trained proportions and recombination type) (`tables.py`).
- `assignment_template.csv`: one row per item, to be copied per participant and filled in later (chunking version, design group, band, introduction weeks, `withheld_alternate`).
- `stimuli/<item>.txt` (ASCII tab, `tab.py`), `.mid` (90 bpm, 3/4) and `_click.mid` (accent on beat 1, percussion channel) (`midi.py`).
- `cues/participant|researcher/<item>.ly` (`cues.py`). `python main.py cues DIR --png` renders them with LilyPond.
- After a search: `input/chunks.csv` and `input/items.csv`. Only bases and generalization items are stored; `check` regenerates alternates, shifts, transpositions and probes from the bases. That makes the round trip exact and keeps hand edits small.

---

## Things I noticed while tracing

1. **Alternate tie-break went the wrong way (implementation, my error; fixed 5 Nov).** `_choose_alternates` preferred *fewer* moved notes when two choices gave alternates to the same number of bases; Q4 asks for as many as neutrality and the band allow. It now counts the moved notes in the alternate items and prefers more.
2. **Staircase bases (design; now Q15).** Under the strict rule, many bases are rising or falling staircases like B1 (C-D-E D-E-F E-F-G F-G-A), where every boundary is a step back of 1 or 2 semitones. The cause is the neutrality rule: a leap usually needs a string change, which is forbidden at the unshared boundaries. So the boundaries that dissociate musical from motor chunks are almost always the weakest-cued ones. Data and options in Q15.
3. **String-pair shifts that use the G string (design note).** Because G is re-entrant, a note moved between the G and C strings changes pitch in the opposite direction from the other notes (−7 against +4 or +5 in B1-shift), so the melody breaks at that point (C5 to D4 at the end of B1-shift). Shifts also bring out-of-key pitches (F#, G#, A#) and break the chunk rules. The spec expects pitches, intervals and contour to change, so this is allowed, but it makes some shifts sound much stranger than others.
4. **`lh` motor identity merges strings (by design, Q8).** C0-C2-C4 (C-D-E) and G0-G2-G4 (G-A-B) count as the same motor chunk under `lh`. This is what the spec asks for, but it means two items with different musical chunks can be identical on the motor model (B2 and R-musical above).
5. **The recombination types are all-or-nothing on the proportions.** "Musical-only" only needs one untrained motor chunk: R-musical has 4 of its 5 motor chunks trained. The analysis uses the proportions directly, so this only matters for the labels.
