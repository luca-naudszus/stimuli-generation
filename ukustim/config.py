"""
config.py
=============================
All parameters of the controlled-stimulus pipeline (build spec v1.6).
Change values here; nothing else is hard-coded. Modules read these values at call time, so a script or a test
can also set them (config.MISALIGNMENT_DEGREE = 3).
"""

SEED = 42

# ---------------------------------------------------------------------------
# Instrument / key (build spec sections 1, 2, 10)
# ---------------------------------------------------------------------------
FRET_MAX = 4                 # first position = frets 0-4
KEY = "C"                    # major key root (name from core.music_theory.NOTE_NAMES); None = free chromatic
FINGER_RULE = "fret"         # left-hand finger = fret number (open string = 0, frets above 4 -> 4)
MAX_STRING_SPAN = 3          # a base uses at most this many ADJACENT strings (G-C-E-A order)

# ---------------------------------------------------------------------------
# Item structure and metre (section 2)
# ---------------------------------------------------------------------------
CHUNK_LEN = 3                # notes per musical chunk
N_CHUNKS = 4                 # musical chunks per item -> N_NOTES = 12
N_NOTES = CHUNK_LEN * N_CHUNKS
BPM = 90                     # one note per beat, quarter notes
BEATS_PER_BAR = 3            # 3/4: one musical chunk = one bar (chunk length must equal this)
EXPORT_CLICK_TRACK = True    # also write <item>_click.mid (accent on beat 1) next to the item MIDI

# ---------------------------------------------------------------------------
# Boundary cue and chunk rules (section 3). Thresholds in semitones.
# ---------------------------------------------------------------------------
LEAP_MIN = 3                 # leap cue: |boundary interval| >= LEAP_MIN and > every within-chunk interval of both chunks
LEAP_MAX = 7                 # maximum leap
ALLOW_LEAP_CUE = True
ALLOW_DIRECTION_CUE = True   # direction change; requires monotonic neighbouring chunks
# Within-chunk intervals must stay below LEAP_MIN (no competing cue); consecutive repeats are forbidden.
ALLOW_CHUNK_REPEAT_IN_ITEM = False   # the same musical chunk twice in one item (implementation choice)
# Turning points inside chunks (build spec v1.4, Q9). 'forbid' = only the 12 monotonic stepwise chunks (prototype).
# 'allow' = X-Y-X chunks are valid again, but at most MAX_TURNING_SHARE of the trained chunks of a set (fallback
# for the prototype: at most 2 of 6; final set: at most one third).
TURNING_POINT_CHUNKS = "forbid"
MAX_TURNING_SHARE = 1 / 3

# ---------------------------------------------------------------------------
# Chunking versions (section 4)
# ---------------------------------------------------------------------------
MISALIGNMENT_DEGREE = 2      # number of musical boundaries NOT in the misaligned motor boundaries (1, 2, 3)
MOTOR_PARTS = (2, 3)         # motor chunk lengths

# ---------------------------------------------------------------------------
# Alternate fingering and played transposition (section 5)
# ---------------------------------------------------------------------------
ALT_MIN_CHUNKS = 2           # alternate fingering used in >= this many chunks of an alternate item
ALT_MIN_NOTES_MOVED = 2
TRANSPOSITION_KEY = "G"      # played transposition: C major -> G major (needs F#); parameter

# ---------------------------------------------------------------------------
# Generalization layer (section 6)
# ---------------------------------------------------------------------------
MOTOR_ONLY_MIN_NEW_MUSICAL = 1   # motor-only recombined item: at least this many of its 4 musical chunks are new
                                 # (strict version = 4; the trained proportions are recorded in the item table)

# ---------------------------------------------------------------------------
# Set search (sections 3, 4, 8)
# ---------------------------------------------------------------------------
N_BASES = 3                  # minimum number of bases
N_BASES_MAX = 6              # the search may use 4-6 bases (Q7)
N_TRAINED_CHUNKS = 6         # trained musical chunks of the prototype set
SEARCH_TRIALS = 3000         # tries per degree (random / exhaustive-triple search)
SEARCH_BUDGET_S = 60         # objective-driven search: seconds per (degree, number of bases)
RDM_THRESHOLD = 0.3          # |r| below this counts as separable

# ---------------------------------------------------------------------------
# Probes (listen-only; section 5, types are parameters)
# ---------------------------------------------------------------------------
PROBE_TRANSPOSITION_SEMITONES = 2
ACCENT_LOUD = 115            # accent variant: loud on the first note of each MISALIGNED motor chunk (regrouping), soft elsewhere
ACCENT_SOFT = 70

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
MIDI_PPQ = 480
MIDI_PROGRAM = 24            # General MIDI 24 = nylon string guitar (no ukulele in GM)
MIDI_VELOCITY = 90
NOTE_GATE = 0.95             # fraction of a beat a note sounds
CLICK_NOTE = 76              # GM percussion (channel 10): 76 = high wood block
CLICK_VEL_ACCENT = 120
CLICK_VEL_SOFT = 70
OUTPUT_DIR = "output"
