"""
config.py
=============================
Central settings for sequence generation, stimulus selection and export.
"""

SEED = 42

# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
PROGRESSION_LENGTH = 4       # chords per progression
MELODY_LENGTH = 8            # tones per melody
ALLOW_CHORD_REPEAT = False   # same chord label twice in a row?
ALLOW_TONE_REPEAT = True     # same tone twice in a row?
MAX_MELODY_LEAP = 5          # max. interval between consecutive tones (semitones)
MAX_FRET = 12                # highest fret used for deriving tone positions

# 'optimal': best variants per label sequence (min. total transition mm, ties: fewest fingers)
# 'random' : variants drawn uniformly (only useful for studying 'unnecessary variation')
VARIANT_MODE = "optimal"

# ---------------------------------------------------------------------------
# Exploration run (python main.py explore)
# ---------------------------------------------------------------------------
N_PROGRESSIONS = 200
N_MELODIES = 200
OUTPUT_DIR = "output"

# Variation check: improvements smaller than this are ignored
VARIATION_TOLERANCE_TRANSITION_MM = 1.0
VARIATION_TOLERANCE_FINGERS = 0.0

# ---------------------------------------------------------------------------
# Stimulus selection (python main.py stimuli)
# ---------------------------------------------------------------------------
STIMULI_DIR = "stimuli"
SET_NAMES = ("A", "B")       # two parallel sets per strand
ITEMS_PER_SET = 50

# Candidate pool per strand (progressions: capped by the number of possible label sequences)
POOL_SIZE = {"progressions": 20000, "melodies": 20000}

# Difficulty = weighted mean of z-scored PHYSICAL features, then percentile rank within the strand
DIFFICULTY_FEATURES = {
    "progressions": {"mean_chord_difficulty_score": 1.0, "mean_transition_physical_mm": 1.0,
                     "max_transition_physical_mm": 1.0, "mean_chord_span_mm": 1.0},
    "melodies":     {"mean_step_distance_mm": 1.0, "max_step_distance_mm": 1.0},
}
DIFFICULTY_PCT_RANGE = (5.0, 95.0)   # difficulty percentiles covered by the ramp
DIFFICULTY_MATCH_WEIGHT = 0.5        # weight of the percentile gap A_i vs B_i when pairing
MIN_CANDIDATES = 15                  # window around the target percentile is widened below this

# Musical features whose spread is maximised within a set and matched between sets A and B.
# out_of_key_ratio is deliberately NOT in this list: it is limited by OUT_OF_KEY_CAP below, and
# rewarding its spread would make the selection prefer out-of-key items whenever the cap allows it.
SELECTION_FEATURES = {
    "progressions": ["mean_minimal_voice_leading", "max_minimal_voice_leading", "common_tone_ratio",
                     "mean_root_motion_fifths", "n_unique_chords"],
    "melodies":     ["mean_interval_semitones", "leap_ratio", "ambitus_semitones",
                     "direction_changes", "n_pitch_classes"],
}

# Only sequences whose variants are optimal for BOTH transition distance and number of fingers
# enter the pool (no 'unnecessary variation' in either sense). Tolerances: VARIATION_TOLERANCE_*.
REQUIRE_NO_AVOIDABLE_COST = True

# Paired items A_i / B_i must not be reversals of each other (identical features!) and may share at
# most this many transitions (unordered label pairs). Reversals are also excluded across the whole selection.
PAIR_MAX_SHARED_TRANSITIONS = {"progressions": 0, "melodies": 1}

# Upper limit for out_of_key_ratio, rising linearly along the difficulty ramp from the first
# to the second value (reached at OUT_OF_KEY_RAMP_END of the set, then constant).
# Idea: lessons start diatonic, accidentals come later. None = no limit.
OUT_OF_KEY_CAP = {"progressions": (0.0, 0.25), "melodies": (0.0, 0.25)}
OUT_OF_KEY_RAMP_END = 0.6

# ---------------------------------------------------------------------------
# Export (tab + MIDI)
# ---------------------------------------------------------------------------
BAR_DURATION_S = 3.0         # duration of one bar in seconds (tempo = 60 * BEATS_PER_BAR / this)
BEATS_PER_BAR = 4            # quarter-note beats per bar (time signature x/4)
MELODY_NOTE_BEATS = 1.0      # note length in beats (1.0 = quarter note, 0.5 = eighth)
CHORD_BARS = 1               # bars per chord (block chord, struck once)
MIDI_PPQ = 480               # ticks per quarter note
MIDI_PROGRAM = 24            # General MIDI: 24 = nylon string guitar (there is no ukulele)
MIDI_VELOCITY = 90