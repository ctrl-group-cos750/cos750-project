# Ctrl Academy brand and UI guide

How Ctrl Academy looks and sounds, for everyone who makes part of it: engineers building screens, and the
instructional design team writing content, recording videos and making slides.

| What | Where |
|---|---|
| Live reference of every component, colour and state | `/ui-kit` on staging: <https://staging.ctrlacademy.co.za/ui-kit> |
| Components (React) | `web/src/components/ui/` (shadcn/ui) and `web/src/components/` (app-level) |
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

The app has one component kit: **shadcn/ui** (style `base-nova`, on Base UI primitives) with Tailwind
CSS, in `web/src/components/ui/`. Its theme in `web/src/styles/global.css` only points at the tokens in
`tokens.css`, so every control uses the brand palette and follows dark mode. Never give the theme a raw
colour, and don't build a control that the kit already has.

```tsx
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AppShell, MasteryStatus } from '../components' // app-level pieces built from the kit
```

| Component | When to use it |
|---|---|
| `Button` (`ui/button`) | `default` for the one main action on a screen; `outline` or `secondary` for other actions; `ghost` for quiet actions like navigation or "Skip example"; `destructive` only for actions that delete or reset; `link` for an action that reads like a link. `loading` while a request runs. `size="lg"` for a page's main actions. |
| `TextField` (`ui/text-field`) | Every text input. Always a visible `label`; `hint` for rules; `error` to say what to fix. Use `Input` and `Label` directly only for inputs `TextField` can't express (file inputs). |
| `Card` (`ui/card`) | A module on the map, a result, a self-contained panel, with `CardHeader`, `CardTitle`, `CardDescription` and `CardContent`. |
| `Alert` (`ui/alert`) | Feedback after an action: `info`, `success`, `warning` or `destructive`, with `AlertTitle` and `AlertDescription`. Each tone has an icon; `destructive` interrupts screen readers, the rest don't. |
| `Badge` (`ui/badge`) | A short inline status next to what it describes ("Locked", "In progress"): `secondary`, `accent`, `success`, `warning`, `destructive`. Pass `icon` when the colour carries meaning. |
| `Progress` (`ui/progress`) | Progress through a module or the whole course. Always give it a `label`. |
| `Spinner` (`ui/spinner`) | While something loads. Its `label` says what. |
| `RadioGroup`, `Separator`, `Input`, `Label` | As in shadcn/ui. |
| `AppShell` | The frame of every page: header, skip link, `<main>`. `width="reading"` for text-heavy pages. Signed-in pages get it, with the shared navigation, from `SignedInLayout`. |
| `MasteryStatus` | Every place an objective's result is shown. Fixes the wording and colours of the three results. |
| `ErrorPage`, `ErrorBoundary` | What a student sees when a page is missing or crashes: plain words and a way back, never a stack trace (NFR-U3). |

Table: The components in the UI kit.

To add a control, add it with `npx shadcn add <name>` (it lands in `web/src/components/ui/`), check it
uses only theme colours, and add it to the `/ui-kit` page and this guide. A new colour goes into
`tokens.css` first; `web/src/styles/tokens.test.ts` checks every text and control pair against WCAG AA
in light and dark mode. Page-specific layout may use Tailwind classes or a CSS module.

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
| Objective (one per learning objective) | Hexagon. Bronze = met with support; gold adds an inner outline and a star = met independently | `--badge-bronze*`, `--badge-gold*` |
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
