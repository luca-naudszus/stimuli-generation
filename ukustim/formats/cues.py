"""
cues.py
=============================
LilyPond export of tab cues, in two flavours (DRAFT, see claude/tab-rendering-options.md):

  participant  tab staff only; fret numbers and a left-hand finger row (0 = open string); NO boundary information:
               no bar lines, no time signature, no chunk labels, equal spacing, identical layout for every item;
               fixed canvas size (build spec section 9: pad, do not crop)
  researcher   notation + tab in 3/4 (one musical chunk per bar, so bar lines are the chunk boundaries), chunk IDs,
               finger row and the aligned / misaligned motor-chunk rows

The .ly text is generated from the stored positions (string, fret, finger), so the picture shows exactly
the fingering the validators checked. Rendering needs the lilypond program (pip package `lilypond`
ships a binary, or install LilyPond itself).

Two LilyPond details that explain the code below:
  - LilyPond numbers strings from the TOP tab line down: string 1 = top line. In ukulele tab the top line is A,
    so A = 1, E = 2, C = 3, G = 4 (ly_string). Each note is written with its string
    (c'4\\3 = C4, a quarter note, on string 3), so LilyPond prints exactly our fret instead of choosing its own.
  - LilyPond's TabStaff does not print left-hand fingerings, so the finger row is a Lyrics line attached to the
    tab voice ("mel"); one syllable per note keeps it aligned.
"""

import os
import shutil
import subprocess
from typing import List, Optional, Sequence

from ukustim import config
from ukustim.core import versions as vs
from ukustim.core.items import Item
from ukustim.core.music_theory import ALL_KEY_ROOTS
from ukustim.core.ukulele_geometry import STRING_ORDER, OPEN_STRING_MIDI

# LilyPond note names (Dutch: 'is' = sharp), index = pitch class
LY_NAMES = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]
VERSION = "2.24.0"


def ly_pitch(midi: int) -> str:
    """MIDI -> LilyPond absolute pitch (60 = c'). Octave marks: ' per octave above c (MIDI 48), ',' below."""
    ticks = midi // 12 - 1 - 3
    return LY_NAMES[midi % 12] + ("'" * ticks if ticks > 0 else "," * (-ticks))


def ly_string(string: str) -> int:
    """LilyPond string number: 1 = top tab line = highest string. Uke order G C E A -> 4 3 2 1."""
    return len(STRING_ORDER) - STRING_ORDER.index(string)


def tuning_ly() -> str:
    """\\stringTuning lists the strings from the highest string NUMBER (lowest line) to string 1."""
    return "\\stringTuning <" + " ".join(ly_pitch(OPEN_STRING_MIDI[s]) for s in STRING_ORDER) + ">"


def _notes(item: Item, with_fingers: bool, with_chunk_marks: bool, chunk_bars: bool) -> str:
    """The note list in LilyPond syntax: quarter notes with their string; optionally fingerings ('-2'), a chunk label
    above the first note of each musical chunk, and explicit bar lines after each chunk."""
    n = config.CHUNK_LEN
    out = []
    for i, (pitch, pos) in enumerate(zip(item.pitches, item.positions)):
        s = f"{ly_pitch(pitch)}4\\{ly_string(pos.string)}"
        if with_fingers and pos.finger > 0:
            s += f"-{pos.finger}"
        if with_chunk_marks and i % n == 0:
            cid = item.chunk_ids[i // n]
            label = cid if not cid.startswith("new:") else "*" + cid.split(":")[-1]      # * = not trained
            s += f"^\\markup {{ \\tiny \"{label}\" }}"
        out.append(s)
        if chunk_bars and (i + 1) % n == 0 and i + 1 < config.N_NOTES:
            out.append('\\bar "|"')
    return " ".join(out)


def _letters(comp: Sequence[int]) -> str:
    """Motor-chunk letters as lyrics syllables ('"A" "A" "A" "B" ...'), one per note."""
    out = []
    for k, p in enumerate(comp):
        out += [chr(ord("A") + k)] * p
    return " ".join(f'"{x}"' for x in out)


# researcher cue: normal page settings, cropped to the content when rendered
PAPER = r"""
\paper {
  indent = 0\mm
  line-width = %(width)d\mm
  ragged-right = ##t
  tagline = ##f
  oddHeaderMarkup = ##f
  evenHeaderMarkup = ##f
  oddFooterMarkup = ##f
  evenFooterMarkup = ##f
}
"""

# participant cue: the page IS the canvas (same size for every item; never cropped)
CANVAS_MM = (200, 38)
PAPER_FIXED = r"""
\paper {
  paper-width = %(w)d\mm
  paper-height = %(h)d\mm
  left-margin = 5\mm
  right-margin = 5\mm
  top-margin = 6\mm
  bottom-margin = 2\mm
  indent = 0\mm
  line-width = %(lw)d\mm
  ragged-right = ##t
  ragged-bottom = ##t
  tagline = ##f
  oddHeaderMarkup = ##f
  evenHeaderMarkup = ##f
  oddFooterMarkup = ##f
  evenFooterMarkup = ##f
}
"""


def participant_ly(item: Item, show_fingers: bool = True) -> str:
    """Tab staff only. No bar lines, time signature or chunk information; all notes are quarter notes spaced
    uniformly, identical layout and canvas size for every item. Left-hand fingers are a lyrics row under the tab
    (LilyPond's TabStaff does not print fingerings itself); open strings show 0 (build spec section 9)."""
    notes = _notes(item, False, False, False)
    fing = " ".join(f'"{p.finger}"' for p in item.positions)
    lyr = f"""
    \\new Lyrics \\with {{ \\override LyricText.font-size = #2 \\override LyricText.font-series = #'bold }}
      \\lyricsto "mel" {{ \\lyricmode {{ {fing} }} }}""" if show_fingers else ""
    return f'''\\version "{VERSION}"
{PAPER_FIXED % dict(w=CANVAS_MM[0], h=CANVAS_MM[1], lw=CANVAS_MM[0] - 10)}
ukuleleTuning = {tuning_ly()}

\\score {{
  <<
    \\new TabStaff \\with {{
      stringTunings = \\ukuleleTuning
      \\omit TimeSignature
      \\omit BarLine
      \\override Stem.stencil = ##f
      \\override Beam.stencil = ##f
      \\override Flag.stencil = ##f
      \\override TabNoteHead.font-size = #2
    }} {{
      \\new TabVoice = "mel" {{ \\cadenzaOn {notes} }}
    }}{lyr}
  >>
  \\layout {{
    \\context {{
      \\Score
      \\override SpacingSpanner.uniform-stretching = ##t
      \\override SpacingSpanner.strict-note-spacing = ##t
      proportionalNotationDuration = #(ly:make-moment 1/8)
    }}
  }}
}}
'''


def ly_key(key) -> str:
    """LilyPond key name for \\key (C for free chromatic)."""
    return "c" if key is None else LY_NAMES[ALL_KEY_ROOTS[key]]


def researcher_ly(item: Item, show_fingers: bool = True) -> str:
    """Notation + tab in 3/4: one musical chunk per bar (bar lines = chunk boundaries); chunk IDs; finger row;
    motor-chunk rows (aligned, misaligned)."""
    notes = _notes(item, show_fingers, True, False)
    fingers = " ".join(f'"{p.finger}"' for p in item.positions)
    al = _letters(vs.aligned_composition())
    mi = _letters(item.composition) if item.composition else al
    return f'''\\version "{VERSION}"
{PAPER % dict(width=260)}
ukuleleTuning = {tuning_ly()}
melody = {{ \\key {ly_key(item.key)} \\major \\time {config.BEATS_PER_BAR}/4 {notes} \\bar "|." }}

\\header {{ title = "{item.item_id}" subtitle = "{item.variant_type}; family {item.family_id}; key {item.key or 'chromatic'}; {config.BPM} bpm" }}

\\score {{
  <<
    \\new Staff {{ \\clef "treble" \\new Voice = "notation" {{ \\melody }} }}
    \\new TabStaff \\with {{ stringTunings = \\ukuleleTuning }} {{
      \\new TabVoice = "mel" {{ \\melody }}
    }}
    \\new Lyrics \\with {{ \\override LyricText.font-size = #-1 }} \\lyricsto "mel" {{ \\set stanza = "LH" \\lyricmode {{ {fingers} }} }}
    \\new Lyrics \\with {{ \\override LyricText.font-size = #-1 }} \\lyricsto "mel" {{ \\set stanza = "Ma" \\lyricmode {{ {al} }} }}
    \\new Lyrics \\with {{ \\override LyricText.font-size = #-1 }} \\lyricsto "mel" {{ \\set stanza = "Mm" \\lyricmode {{ {mi} }} }}
  >>
  \\layout {{ }}
}}
'''


def lilypond_binary() -> Optional[str]:
    """Path of the lilypond program: on PATH, or the binary shipped by the pip package `lilypond`; None if absent."""
    exe = shutil.which("lilypond")
    if exe:
        return exe
    try:
        import lilypond
        return str(lilypond.executable())
    except Exception:
        return None


def render(ly_path: str, fmt: str = "png", dpi: int = 300, crop: bool = True) -> str:
    """Run lilypond on ly_path; returns the output path. fmt: png | svg | pdf. crop=False keeps the page as the
    canvas (participant cues); crop=True trims it to the content (researcher cues)."""
    exe = lilypond_binary()
    if exe is None:
        raise RuntimeError("lilypond not found: install LilyPond or `pip install lilypond`")
    base = os.path.splitext(ly_path)[0]
    cmd = [exe] + (["-dcrop"] if crop else []) + ["-o", base]     # -dcrop trims the page to the music
    if fmt == "png":
        cmd += ["--png", f"-dresolution={dpi}"]
    elif fmt == "svg":
        cmd += ["-dbackend=svg"]
    elif fmt != "pdf":
        raise ValueError(f"unknown format {fmt}")
    cmd.append(ly_path)
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = base + (".cropped." if crop else ".") + fmt
    if res.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"lilypond failed for {ly_path}:\n{res.stderr[-800:]}")
    return out


def svg_fret_digits(svg_path: str) -> List[tuple]:
    """(x, y, text) of every <text> in a rendered tab SVG, left to right. Used to check that the picture
    shows exactly the frets of the item (fret digits and, in the participant cue, the finger row)."""
    import re
    s = open(svg_path).read()
    out = []
    for m in re.finditer(r'<g transform="translate\(([-\d.]+), ([-\d.]+)\)">\s*<text[^>]*>\s*<tspan>([^<]*)</tspan>', s):
        out.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return sorted(out)


def export_cues(items: Sequence[Item], outdir: str, formats: Sequence[str] = (), show_fingers: bool = True) -> None:
    """Write .ly files (and images if formats given) for every played item: participant/ (fixed canvas) and
    researcher/ (cropped)."""
    for kind, fn in (("participant", participant_ly), ("researcher", researcher_ly)):
        crop = kind == "researcher"
        d = os.path.join(outdir, kind)
        os.makedirs(d, exist_ok=True)
        for it in items:
            if not it.played:
                continue
            path = os.path.join(d, f"{it.item_id}.ly")
            open(path, "w").write(fn(it, show_fingers))
            for fmt in formats:
                render(path, fmt, crop=crop)
