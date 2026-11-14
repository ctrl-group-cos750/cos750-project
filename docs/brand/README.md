# Ctrl Academy brand and UI guide

How Ctrl Academy looks and sounds, for everyone who makes part of it: engineers building screens, and the
instructional design team writing content, recording videos and making slides.

| What | Where |
|---|---|
| Live reference of every component, colour and state | `/ui-kit` on staging: <https://staging.ctrlacademy.co.za/ui-kit> |
| Components (React) | `web/src/components/` |
| Design tokens (colours, type, spacing) | `web/src/styles/tokens.css` |
| Logo pack (SVG and PNG) | `assets/`, with its own `assets/README.md` |

## Principles

1. **Calm and clear.** The student is learning something new. Every screen has one main action, plenty of
   space and nothing decorative competing with the content.
2. **Never colour alone.** Every state has a colour *and* a word, symbol or shape (SE document NFR-A2).
3. **Encouraging, not judging.** Wrong answers and "not yet" results tell the student what to do next.
4. **Consistent.** Use the kit. A screen that needs something the kit lacks gets it added to the kit, not
   built one-off.

## Logo

The logo is the **Ctrl keycap**. Use the files in `assets/` as they are: never redraw, recolour, stretch or
add effects to them.

| Placement | File |
|---|---|
| App header, favicon, small spaces | `assets/svg/mark.svg` (the keycap alone) |
| Slides, video title cards, light backgrounds | `assets/svg/logo-horizontal.svg` |
| Dark backgrounds | `assets/svg/logo-horizontal-reversed.svg` |
| Document covers, square spaces | `assets/svg/logo-stacked.svg` |

Leave clear space around the logo of at least half the keycap's width. The product is called
**Ctrl Academy**; the team is **Control Group** ("Ctrl Group" is fine informally).

## Colour

The brand colour is **Ctrl blue `#2470C9`**. In code, always use the token, never the hex value: the values
change in dark mode.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-bg` | `#FAFAF7` | `#141413` | Page background |
| `--color-surface` | `#FFFFFF` | `#1F1F1D` | Cards, inputs, header |
| `--color-text` | `#141413` | `#FAFAF7` | Body text |
| `--color-text-muted` | `#5C5B55` | `#A8A79F` | Hints, captions, secondary text |
| `--color-border` | `#8A897F` | `#76756D` | Input and control borders |
| `--color-accent` | `#2470C9` | `#2470C9` | Primary buttons, progress, focus ring |
| `--color-accent-text` | `#2470C9` | `#7FB2EE` | Links and accent text |
| `--color-success` | `#1E7A3C` | `#5CC480` | Correct answers, met objectives |
| `--color-warning` | `#8F5400` | `#F0B44C` | Hints that cost support, "not yet" |
| `--color-danger` | `#B42318` | `#F97066` | Errors and destructive actions only |

Table: The main colour tokens. Every text colour meets WCAG 2.1 AA (at least 4.5:1) on the backgrounds it
is used on; control borders meet 3:1.

### Page backgrounds

A student chooses the page background (SE FR-9.9): **Glow** (the default), **Doodles** or **Plain**, set as
`data-bg` on `<html>` and painted by `web/src/styles/backgrounds.css` behind everything. Nothing moves.
Forced colours and print always get the plain page.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg-glow-blue` | `rgb(36 112 201 / 28%)` | `rgb(0 62 150 / 70%)` | Glow, top-left corner |
| `--bg-glow-gold` | `rgb(246 193 85 / 42%)` | `rgb(120 78 8 / 60%)` | Glow, bottom-right corner (honey) |
| `--bg-glow-blue-faint` | `rgb(36 112 201 / 14%)` | `rgb(0 62 150 / 40%)` | Glow, top-right corner |
| `--bg-glow-soft-blue`, `--bg-glow-soft-gold` | 10%, 24% | 55%, 45% | The gentler glows behind the doodles |
| `--doodle-ink` | `rgb(36 112 201 / 16%)` | `rgb(128 187 255 / 11%)` | The doodle wallpaper (`assets/doodles.svg`, a mask) |
| `--surface-tinted` | `rgb(255 255 255 / 88%)` | `rgb(38 38 38 / 86%)` | Cards on the module map, badges and report |
| `--color-surface-solid` | as `--color-surface` | as `--color-surface` | Popups, menus and notes: always opaque |
| `--muted-foreground` with a background | `rgb(84 84 84)` | `rgb(176 176 176)` | Muted text, darker (lighter in dark) |
| `--color-accent-text` with a background | `--accent-foreground` `rgb(13 79 165)` | `rgb(179 214 255)` | Links |

Table: Background tokens. Text keeps 4.5:1 at the strongest point of every glow and on a tinted card over
it (`web/src/styles/contrast.test.ts`). Lessons, activities, the quick check, the profile and staff pages keep
solid cards: decoration stays away from reading.

**Red is for errors only**, such as a failed save or a destructive button. A wrong answer or a "not yet"
result is not an error: use the warning (amber) tone and explain what to try next.

## Type

| Role | Typeface | Token |
|---|---|---|
| Headings, buttons, the logo | Space Grotesk | `--font-display` |
| Body text | The device's system font | `--font-body` |
| Code, vertex labels, the queue and visited set | JetBrains Mono | `--font-mono` |

Use the type scale (`--text-sm` to `--text-3xl`), not pixel sizes. Headings are sentence case
("Meet BFS", not "Meet Bfs" or "MEET BFS"). Don't put small labels or tags above headings: the heading
says what the section is.

## Components

Import from `web/src/components`:

```tsx
import { AppShell, Button, Card, TextField } from '../components'
```

| Component | When to use it |
|---|---|
| `AppShell` | The frame of every signed-in page: header, skip link, `<main>`. `width="reading"` for text-heavy pages. |
| `Button` | `primary` for the one main action on a screen; `secondary` for other actions; `ghost` for low-emphasis actions like "Skip example"; `danger` only for actions that delete or reset. `loading` while a request runs. |
| `TextField` | Every text input. Always a visible `label`; `hint` for rules; `error` to say what to fix. |
| `Card` | A module on the map, a result, a self-contained panel. `interactive` when the whole card is clickable. |
| `Alert` | Feedback after an action: `info`, `success`, `warning` or `danger`. |
| `Tag` | A short inline status next to what it describes ("Locked", "In progress"). |
| `MasteryStatus` | Every place an objective's result is shown. Fixes the wording and colours of the three results. |
| `ProgressBar` | Progress through a module or the whole course. Always give it a `label`. |
| `Spinner` | While something loads. Its `label` says what. |

Table: The components in the UI kit.

To add a component or a token, open a PR that adds it to `web/src/components/` (with tests), to the
`/ui-kit` page and to this guide.

## Learning states

These are fixed across the whole app so students learn them once.

| State | Shown as |
|---|---|
| Met independently | Green, ✓, "Met independently" |
| Met with support | Blue, ◐, "Met with support" |
| Not yet | Amber, ○, "Not yet", always with what to review next |

Table: Mastery results (ID document §3.2, SE document FR-7.2), shown with `MasteryStatus`.

| BFS vertex | Shown as |
|---|---|
| Unvisited | Plain outline, no symbol |
| Queued | Amber outline, "…" |
| Current | Solid Ctrl blue with white label, "▶" |
| Visited | Green outline, "✓" |

Table: BFS visualiser vertex states (tokens `--bfs-*`). Edges already traversed are drawn thicker in Ctrl
blue. The `/ui-kit` page has a working example.

## Badges

Badges are private (FR-9.4) and drawn by `AchievementBadge` from the catalogue in
`web/src/components/achievements.ts`; see them all on `/ui-kit`. Don't draw badges elsewhere.

| Kind | Shape | Colour tokens |
|---|---|---|
| Objective (one per learning objective) | Hexagon in three levels. Practised = an accent outline with no fill (secure in practice); bronze = met with support; gold adds an inner outline and a star = met independently | accent, `--badge-bronze*`, `--badge-gold*` |
| Milestone (Ready for the Lecture, Came Back Stronger, Solo Run) | Medal with ribbons | accent |
| Quest | Shield | success |
| Hidden (Off the Map) | Diamond; shows "?" until found | accent |
| Not earned yet | The same shape, dashed and faded, with a padlock | `--color-border` |

Badge wording names the skill or the strategy ("You traced BFS by hand, level by level"), never the
student ("You're a genius"), and no badge marks a failure. There are no streak, speed, "perfect" or
rank badges.

## Writing in the app

- **Talk to the student** as "you". Short sentences, plain words. Define a term the first time it appears.
- **Feedback explains why.** "Not quite: D was queued before E, so D comes out first." rather than "Wrong."
- **Buttons say what they do**: "Check answer", "Show a hint", "Next step", not "Submit" or "OK".
- **Errors say what to do next**: "Enter an email address like name@tuks.co.za."
- **Warn before a cost**: hint levels 3 and 4 say up front that using them counts as "met with support".
- **UK English** spelling (colour, organise), to match the documents.
- Code, vertex names and Python keywords are in `--font-mono`.

## Videos and slides

- Start each video with a title card: `logo-horizontal.svg` on `--color-bg`, the module title in Space
  Grotesk. End with the same card and "Next: …".
- Draw graphs in videos with the same vertex states and colours as the visualiser, so what students see in a
  video matches what they then use.
- Every video has captions and a transcript (NFR-A4).
- Slides use the light background, Ctrl blue for emphasis, and the horizontal logo in a corner.

## Accessibility checklist

Before a screen is done (SE document NFR-A1 to NFR-A4):

- [ ] Everything works with the keyboard alone, in a sensible order, with a visible focus ring.
- [ ] Every input has a visible label; every image or diagram has a text alternative.
- [ ] No state is shown by colour alone.
- [ ] Only colours from the tokens, so contrast is already checked.
- [ ] It reads properly at 200% zoom and on a phone (390 px wide) without sideways scrolling.
- [ ] Animations respect "reduce motion" (the base styles handle this for CSS).
