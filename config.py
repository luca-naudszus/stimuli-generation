"""
config.py
=============================
Central settings for sequence generation and evaluation.
"""

SEED = 42

# Number of generated sequences (default for main.py)
N_PROGRESSIONS = 200
N_MELODIES = 200

# Sequence lengths
PROGRESSION_LENGTH = 4   # chords per progression
MELODY_LENGTH = 8        # tones per melody

# Generation rules
ALLOW_CHORD_REPEAT = False   # same chord label twice in a row?
MAX_MELODY_LEAP = 5          # max. interval between consecutive tones (semitones)
ALLOW_TONE_REPEAT = True     # same tone twice in a row?

# Instrument: highest fret used for deriving tone positions
MAX_FRET = 12

# Variation check: improvements smaller than this are ignored
VARIATION_TOLERANCE_TRANSITION_MM = 1.0
VARIATION_TOLERANCE_FINGERS = 0.0

OUTPUT_DIR = "output"