"""
export.py
=============================
Writes the researcher-facing files of a set: ASCII tabs and MIDI per item (plus the click track).
LilyPond cues are in cues.py, tables in tables.py.
"""

import os
from typing import Sequence

from ukustim import config
from ukustim.core.items import Item
from ukustim.formats.midi import build_click_midi, build_midi
from ukustim.formats.tab import tab_item


def export_items(items: Sequence[Item], outdir: str) -> None:
    """For every item: <id>.txt (tab), <id>.mid, and <id>_click.mid if EXPORT_CLICK_TRACK; plus all_tabs.txt."""
    os.makedirs(outdir, exist_ok=True)
    tabs = []
    for it in items:
        t = tab_item(it)
        tabs.append(t)
        open(os.path.join(outdir, f"{it.item_id}.txt"), "w").write(t)
        open(os.path.join(outdir, f"{it.item_id}.mid"), "wb").write(build_midi(it))
        if config.EXPORT_CLICK_TRACK:
            open(os.path.join(outdir, f"{it.item_id}_click.mid"), "wb").write(build_click_midi(it))
    open(os.path.join(outdir, "all_tabs.txt"), "w").write("\n".join(tabs))
