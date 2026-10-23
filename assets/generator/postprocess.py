#!/usr/bin/env python3
"""favicon.ico, the preview sheet and the pack README. Called by build.py."""
import os
import sys

from PIL import Image, ImageDraw

out, accent = sys.argv[1], sys.argv[2]
P = lambda *a: os.path.join(out, *a)

# favicon.ico from the 48px icon (16/32/48 layers)
Image.open(P("png/icon/icon-48.png")).save(P("png/icon/favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

# preview sheet: light half / dark half
W, H = 1600, 1000
sheet = Image.new("RGB", (W, H), "#FAFAF7")
d = ImageDraw.Draw(sheet)
d.rectangle([0, H // 2, W, H], fill="#141413")

def paste(path, x, y, h=None):
    im = Image.open(path).convert("RGBA")
    if h:
        im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    sheet.paste(im, (x, y), im)
    return im

paste(P("png/logo-horizontal/logo-horizontal-h320.png"), 80, 90, 200)
paste(P("png/logo-square/logo-1024-light.png"), 1160, 50, 400)
x = 80
for s in (128, 64, 48, 32, 16):
    paste(P(f"png/icon/icon-{s}.png"), x, 360 + (128 - s))
    x += s + 32

paste(P("png/logo-horizontal/logo-horizontal-reversed-h320.png"), 80, H // 2 + 90, 200)
paste(P("png/logo-square/logo-1024-dark.png"), 1160, H // 2 + 50, 400)
paste(P("png/logo-square/logo-stacked-reversed-transparent-1024.png"), 780, H // 2 + 100, 300)
sheet.save(P("preview.png"))

# README
from build import shade  # noqa: E402  (same folder)
edge = shade(accent, 0.66)
readme = f"""# Control Group — logo pack (Concept A, Ctrl keycap)

Accent (Smartie colour): `{accent}`   Keycap edge: `{edge}`   Ink: `#141413`   Paper: `#FAFAF7`

All text is outlined to paths; the SVGs need no fonts installed.
Typefaces used at build time: Space Grotesk Bold (wordmark), JetBrains Mono Bold (key label).

## Files

svg/                      Masters. Use these wherever a vector is accepted (Canva, slides, print).
  mark.svg                  The keycap alone. Square. This is the icon.
  icon-padded.svg           Keycap with a safe margin, for platforms that mask icons into circles.
  logo-horizontal.svg       Keycap + "Group", dark text. For light backgrounds.
  logo-horizontal-reversed.svg   Same, white text. For dark backgrounds.
  logo-stacked.svg          Keycap above "Group". For square placements.
  logo-stacked-reversed.svg
  logo-square-*.svg         1024x1024 compositions: transparent / light / dark.

png/icon/                 icon-16 ... icon-1024 (transparent), icon-maskable-512, favicon.ico
png/logo-horizontal/      logo-horizontal(-reversed)-h160/320/640/1280 (transparent),
                          plus one each flattened on light and dark at h320
png/logo-square/          logo-1024-transparent / -light / -dark, logo-512-light,
                          logo-stacked(-reversed)-transparent-1024 (tight crop, no margin)
preview.png               Contact sheet of the above.
generator/                The build. See "Rebuilding" below.

## Where each one goes

GitHub org/repo avatar, WhatsApp group photo:  png/logo-square/logo-1024-light.png
Slide header / footer:                         svg/logo-horizontal.svg (or -reversed on dark slides)
App favicon:                                   png/icon/favicon.ico, icon-32.png
App icon / PWA manifest:                       icon-192 is not shipped; render from mark.svg, or use icon-256 / icon-512
Document cover:                                svg/logo-stacked.svg

## Rebuilding in another colour

    cd generator
    npm install
    pip install fonttools brotli uharfbuzz pillow
    python3 build.py --accent "#D93A3A"      # writes generator/dist/

Everything is derived from --accent: the keycap edge is the accent at 66% brightness,
the key label stays white. Check white-on-accent contrast if the winning Smartie is
yellow, orange or pink: those will need a dark label (`WHITE` in build.py -> `INK`).

Fonts in generator/vendor-fonts/ are Space Grotesk and JetBrains Mono, both under the
SIL Open Font License (licences alongside).
"""
with open(P("README.md"), "w") as fh:
    fh.write(readme)
print("favicon, preview, README written")
