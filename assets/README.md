# Control Group — logo pack (Concept A, Ctrl keycap)

Accent (Smartie colour): `#2470C9`   Keycap edge: `#184a85`   Ink: `#141413`   Paper: `#FAFAF7`

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
