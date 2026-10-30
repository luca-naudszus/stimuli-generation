"""
config.py
=============================
All parameters of the controlled-stimulus pipeline (build spec v1.3).
Change values here; nothing else is hard-coded.
"""

SEED = 42

# ---------------------------------------------------------------------------
# Instrument / key (build spec sections 1, 2, 10)
# ---------------------------------------------------------------------------
FRET_MAX = 4                 # first position = frets 0-4
KEY = "C"                    # major key root (name from music_theory.NOTE_NAMES); None = free chromatic
FINGER_RULE = "fret"         # left-hand finger = fret number (open string = 0, frets above 4 -> 4)
MAX_STRING_SPAN = 3          # a base uses at most this many ADJACENT strings (G-C-E-A order)

# ---------------------------------------------------------------------------
# Item structure (section 2)
# ---------------------------------------------------------------------------
CHUNK_LEN = 3                # notes per musical chunk
N_CHUNKS = 4                 # musical chunks per item -> N_NOTES = 12
N_NOTES = CHUNK_LEN * N_CHUNKS
BPM = 90                     # one note per beat, quarter notes, 4/4
BEATS_PER_BAR = 4

# ---------------------------------------------------------------------------
# Boundary cue (section 3). Thresholds in semitones.
# ---------------------------------------------------------------------------
LEAP_MIN = 3                 # leap cue: |boundary interval| >= LEAP_MIN and > every within-chunk interval
LEAP_MAX = 7                 # maximum leap
ALLOW_LEAP_CUE = True
ALLOW_DIRECTION_CUE = True   # direction change; requires monotonic neighbouring chunks
# Within-chunk intervals must stay below LEAP_MIN (no competing cue); consecutive repeats are forbidden.
ALLOW_CHUNK_REPEAT_IN_ITEM = False   # the same musical chunk twice in one item (implementation choice)

# ---------------------------------------------------------------------------
# Chunking versions (section 4)
# ---------------------------------------------------------------------------
MISALIGNMENT_DEGREE = 2      # number of musical boundaries NOT in the misaligned motor boundaries (1, 2, 3)
MOTOR_PARTS = (2, 3)         # motor chunk lengths

# ---------------------------------------------------------------------------
# Alternate fingering (section 5)
# ---------------------------------------------------------------------------
ALT_MIN_CHUNKS = 2           # alternate fingering used in >= this many chunks of an alternate item
ALT_MIN_NOTES_MOVED = 2

# ---------------------------------------------------------------------------
# Prototype set search (feasibility)
# ---------------------------------------------------------------------------
N_BASES = 3                  # minimum 3; more bases make recurrence easier
N_TRAINED_CHUNKS = 6
SEARCH_TRIALS = 3000         # random chunk subsets tried per degree
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
OUTPUT_DIR = "output"
