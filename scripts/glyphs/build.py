#!/usr/bin/env python3
"""Freeze Geist into outlines the card renderer can use offline.

A README loads the card as an <img>, which can neither fetch a web font nor
count on any particular system font, so the card's type is drawn as paths.
This script instances the Geist variable font at the weights the card uses and
writes, per weight, the outline, advance and pair kerning of every printable
ASCII character to geist-<weight>.json next to it.

A development tool, not part of the daily run: it needs fontTools and
uharfbuzz, which the workflow does not install. Rerun it only to change the
typeface, the weights or the character set:

    pip install fonttools uharfbuzz
    python3 scripts/glyphs/build.py 'Geist[wght].ttf' 400 500

The outlines are a rendering of Geist (SIL Open Font License 1.1, see OFL.txt
in this directory).
"""

import io
import json
import os
import sys

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

CHARS = [chr(c) for c in range(32, 127)] + list("·–—’")
HERE = os.path.dirname(os.path.abspath(__file__))


def build(path, weight):
    font = instancer.instantiateVariableFont(TTFont(path), {"wght": weight})
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    tt = TTFont(io.BytesIO(data))
    cmap, gs = tt.getBestCmap(), tt.getGlyphSet()
    shaper = hb.Font(hb.Face(data))

    glyphs = {}
    for ch in CHARS:
        if ord(ch) not in cmap:
            continue
        pen = SVGPathPen(gs, ntos=lambda v: "%.0f" % v)
        gs[cmap[ord(ch)]].draw(pen)
        glyphs[ch] = {"adv": gs[cmap[ord(ch)]].width, "d": pen.getCommands()}

    # Kerning as harfbuzz applies it, flattened to pairs: shape every pair once
    # and keep the ones whose advance differs from the two glyphs set apart.
    kern = {}
    present = [c for c in glyphs if c != " "]
    for a in present:
        for b in present:
            run = hb.Buffer()
            run.add_str(a + b)
            run.guess_segment_properties()
            hb.shape(shaper, run, {"kern": True, "liga": False})
            pos = run.glyph_positions
            if len(pos) == 2 and pos[0].x_advance != glyphs[a]["adv"]:
                kern[a + b] = pos[0].x_advance - glyphs[a]["adv"]

    dest = os.path.join(HERE, "geist-%d.json" % weight)
    with open(dest, "w") as fh:
        json.dump({"family": "Geist", "weight": weight,
                   "license": "SIL Open Font License 1.1 - see OFL.txt",
                   "unitsPerEm": tt["head"].unitsPerEm, "glyphs": glyphs, "kern": kern},
                  fh, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    print("%d glyphs, %d kerning pairs -> %s" % (len(glyphs), len(kern), dest))


def main():
    path, weights = sys.argv[1], [int(w) for w in sys.argv[2:]] or [400, 500]
    for weight in weights:
        build(path, weight)


if __name__ == "__main__":
    main()
