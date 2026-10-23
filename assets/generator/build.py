#!/usr/bin/env python3
"""Control Group — logo asset generator (Concept A: the Ctrl keycap).

    python3 build.py --accent "#2470C9"          # rebuild the whole pack
    python3 build.py --accent "#D93A3A" --out dist-red

Everything downstream of --accent is derived: the keycap edge is the accent
darkened, the text is outlined to SVG paths (no font dependency), and
render.mjs rasterises the PNG sizes from the SVG masters.
"""
import argparse
import json
import os
import shutil
import subprocess

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "vendor-fonts")
INK = "#141413"
PAPER = "#FAFAF7"
WHITE = "#FFFFFF"


# ----------------------------------------------------------------- colour --
def _rgb(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(hexstr, f):
    """Multiply each channel by f (0.66 = the keycap edge)."""
    r, g, b = _rgb(hexstr)
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * f))) for v in (r, g, b))


# ------------------------------------------------------------------- type --
class Face:
    def __init__(self, filename):
        path = os.path.join(FONT_DIR, filename)
        self.tt = TTFont(path)
        self.upem = self.tt["head"].unitsPerEm
        self.asc = self.tt["hhea"].ascent / self.upem
        self.desc = -self.tt["hhea"].descent / self.upem
        self.glyphset = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.hbfont = hb.Font(hb.Face(hb.Blob.from_file_path(path)))

    def shape(self, text, size, tracking=0.0):
        """Shape with kerning; returns ([(gid, x, y)], advance_width)."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True, "liga": True})
        k = size / self.upem
        x, glyphs = 0.0, []
        infos, poss = buf.glyph_infos, buf.glyph_positions
        for i, (info, pos) in enumerate(zip(infos, poss)):
            glyphs.append((info.codepoint, x + pos.x_offset * k, -pos.y_offset * k))
            x += pos.x_advance * k
            if i < len(infos) - 1:
                x += tracking * size
        return glyphs, x

    def baseline(self, size, line_height, box_top):
        """Where CSS puts the baseline of a one-line box of `line_height`."""
        content = (self.asc + self.desc) * size
        half_leading = (line_height * size - content) / 2
        return box_top + half_leading + self.asc * size

    def word(self, text, size, x, baseline, fill, tracking=0.0):
        """Outline `text` as one <path>; returns (svg, ink_bbox)."""
        glyphs, adv = self.shape(text, size, tracking)
        k = size / self.upem
        d, bbox = [], [1e9, 1e9, -1e9, -1e9]
        for gid, gx, gy in glyphs:
            name = self.order[gid]
            glyph = self.glyphset[name]
            pen = SVGPathPen(self.glyphset)
            glyph.draw(TransformPen(pen, (k, 0, 0, -k, x + gx, baseline + gy)))
            d.append(pen.getCommands())
            bp = BoundsPen(self.glyphset)
            glyph.draw(bp)
            if bp.bounds:
                x0, y0, x1, y1 = bp.bounds
                bbox[0] = min(bbox[0], x + gx + x0 * k)
                bbox[2] = max(bbox[2], x + gx + x1 * k)
                bbox[1] = min(bbox[1], baseline + gy - y1 * k)
                bbox[3] = max(bbox[3], baseline + gy - y0 * k)
        svg = '<path fill="%s" d="%s"/>' % (fill, "".join(d))
        return svg, bbox, adv


# ---------------------------------------------------------------- pieces --
def keycap(x, y, s, accent, mono):
    """The Ctrl key. Geometry is Concept A's 160px keycap, scaled by s/160."""
    k = s / 160.0
    edge = shade(accent, 0.66)
    out = []
    out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="%s"/>'
               % (x, y, s, s, 26 * k, edge))
    fx, fy, fw, fh = x + 11 * k, y + 7 * k, s - 22 * k, s - 26 * k
    out.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="%s"/>'
               % (fx, fy, fw, fh, 19 * k, accent))
    size = 42 * k
    box_top = fy + fh - 14 * k - size          # flex-end, padding-bottom 14, line-height 1
    base = mono.baseline(size, 1.0, box_top)
    svg, _, _ = mono.word("Ctrl", size, fx + 18 * k, base, WHITE, tracking=-0.02)
    out.append(svg)
    return "\n".join(out)


def svg_doc(w, h, body, background=None):
    bg = '<rect width="%.2f" height="%.2f" fill="%s"/>\n' % (w, h, background) if background else ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.2f %.2f" width="%.2f" height="%.2f">\n%s%s\n</svg>\n'
            % (w, h, w, h, bg, body))


# --------------------------------------------------------------- lockups --
def build_masters(accent):
    grotesk = Face("SpaceGrotesk-Bold.ttf")
    mono = Face("JetBrainsMono-Bold.ttf")
    masters = {}

    # 1. Mark: the keycap alone (also the app icon).
    masters["mark"] = svg_doc(160, 160, keycap(0, 0, 160, accent, mono))

    # 2. Horizontal lockup: keycap + "Group" (Concept A as drawn).
    def horizontal(text_fill):
        size, lh, gap = 124, 0.9, 40
        box_top = (160 - lh * size) / 2
        base = grotesk.baseline(size, lh, box_top)
        word, bbox, _ = grotesk.word("Group", size, 160 + gap, base, text_fill, tracking=-0.05)
        w = bbox[2]
        return svg_doc(w, 160, keycap(0, 0, 160, accent, mono) + "\n" + word)

    masters["logo-horizontal"] = horizontal(INK)
    masters["logo-horizontal-reversed"] = horizontal(WHITE)

    # 3. Stacked lockup: keycap above "Group" (square-ish, for avatars).
    def stacked(text_fill):
        size, lh, gap = 72, 0.9, 24
        _, adv = grotesk.shape("Group", size, -0.05)
        probe, bbox, _ = grotesk.word("Group", size, 0, 0, text_fill, tracking=-0.05)
        ink_w = bbox[2] - bbox[0]
        w = max(160, ink_w)
        tx = (w - ink_w) / 2 - bbox[0]
        base = grotesk.baseline(size, lh, 160 + gap)
        word, bbox2, _ = grotesk.word("Group", size, tx, base, text_fill, tracking=-0.05)
        h = bbox2[3]
        return svg_doc(w, h, keycap((w - 160) / 2, 0, 160, accent, mono) + "\n" + word), (w, h)

    masters["logo-stacked"], stacked_dims = stacked(INK)
    masters["logo-stacked-reversed"], _ = stacked(WHITE)

    # 4. 1024×1024 squares: the stacked lockup centred with ~14% margins.
    def square(inner_svg, background):
        w, h = stacked_dims
        inner = inner_svg.split("\n", 1)[1].rsplit("</svg>", 1)[0]
        scale = (1024 * 0.72) / max(w, h)
        ox = (1024 - w * scale) / 2
        oy = (1024 - h * scale) / 2
        body = '<g transform="translate(%.2f %.2f) scale(%.4f)">\n%s\n</g>' % (ox, oy, scale, inner)
        return svg_doc(1024, 1024, body, background)

    masters["logo-square-transparent"] = square(masters["logo-stacked"], None)
    masters["logo-square-light"] = square(masters["logo-stacked"], PAPER)
    masters["logo-square-dark"] = square(masters["logo-stacked-reversed"], INK)

    # 5. Icon with safe-area padding (maskable / rounded-mask platforms).
    masters["icon-padded"] = svg_doc(
        160, 160,
        keycap(16, 16, 128, accent, mono))

    return masters


# ---------------------------------------------------------------- render --
RENDER_JOBS = [
    # (master, out path, fit mode, value, background)
    *[("mark", f"png/icon/icon-{s}.png", "width", s, None) for s in (16, 32, 48, 64, 128, 256, 512, 1024)],
    ("icon-padded", "png/icon/icon-maskable-512.png", "width", 512, None),
    *[("logo-horizontal", f"png/logo-horizontal/logo-horizontal-h{h}.png", "height", h, None) for h in (160, 320, 640, 1280)],
    *[("logo-horizontal-reversed", f"png/logo-horizontal/logo-horizontal-reversed-h{h}.png", "height", h, None) for h in (160, 320, 640, 1280)],
    ("logo-horizontal", "png/logo-horizontal/logo-horizontal-on-light-h320.png", "height", 320, PAPER),
    ("logo-horizontal-reversed", "png/logo-horizontal/logo-horizontal-on-dark-h320.png", "height", 320, INK),
    ("logo-stacked", "png/logo-square/logo-stacked-transparent-1024.png", "height", 1024, None),
    ("logo-stacked-reversed", "png/logo-square/logo-stacked-reversed-transparent-1024.png", "height", 1024, None),
    ("logo-square-transparent", "png/logo-square/logo-1024-transparent.png", "width", 1024, None),
    ("logo-square-light", "png/logo-square/logo-1024-light.png", "width", 1024, None),
    ("logo-square-dark", "png/logo-square/logo-1024-dark.png", "width", 1024, None),
    ("logo-square-light", "png/logo-square/logo-512-light.png", "width", 512, None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accent", default="#2470C9", help="Smartie colour, hex")
    ap.add_argument("--out", default="dist", help="output folder (wiped)")
    args = ap.parse_args()

    out = os.path.join(HERE, args.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "svg"))
    for sub in ("png/icon", "png/logo-horizontal", "png/logo-square"):
        os.makedirs(os.path.join(out, sub))

    masters = build_masters(args.accent)
    for name, svg in masters.items():
        with open(os.path.join(out, "svg", name + ".svg"), "w") as fh:
            fh.write(svg)

    jobs = [{"svg": os.path.join(out, "svg", m + ".svg"),
             "out": os.path.join(out, p), "mode": mode, "value": v, "background": bg}
            for m, p, mode, v, bg in RENDER_JOBS]
    with open(os.path.join(out, "render-jobs.json"), "w") as fh:
        json.dump(jobs, fh)
    subprocess.run(["node", os.path.join(HERE, "render.mjs"), os.path.join(out, "render-jobs.json")], check=True)

    subprocess.run(["python3", os.path.join(HERE, "postprocess.py"), out, args.accent], check=True)
    os.remove(os.path.join(out, "render-jobs.json"))
    print("accent", args.accent, "edge", shade(args.accent, 0.66), "->", out)


if __name__ == "__main__":
    main()
