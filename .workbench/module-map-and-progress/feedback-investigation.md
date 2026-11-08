# Debug Investigation — module-map-and-progress

## Reported Issue

Two UI bugs on the `feature/module-map-and-progress` branch:

1. **Bug 1 (ModulePage — "Finish module" dead end):** On the last segment of a module, clicking
   "Finish module" does nothing visibly — no navigation, no completion feedback. The module IS
   marked complete on the backend, but the student is left on the same screen with no indication
   of what happened or what to do next.

2. **Bug 2 (ModuleMap — cards not clickable):** On the module map, clicking a module row/card
   does NOT navigate to that module. Only the "Continue module N →" button at the bottom of the
   page navigates to a module. Open, in-progress, and complete module cards are all non-interactive
   from a navigation standpoint (clicking anywhere on the card except the Continue button does
   nothing).

---

## Investigation Process

### Artifacts reviewed
- `.workbench/module-map-and-progress/review.md` — the review explicitly flags both issues.
  Under MINOR items: *"Finish module button re-saves position without navigating away"*
  (`ModulePage.tsx:60–62`) and notes the UX gap. Under Deferred items in the re-review:
  *"Finish-module UX … student stays on the last segment after clicking 'Finish module' with no
  navigation or completion banner."* The card-clickability gap is confirmed by a test that was
  explicitly written to document the current (broken) behaviour:
  `'open module card is not wrapped in an anchor either (uses navigate button)'`.

- `.workbench/module-map-and-progress/dev-notes.md` — confirms the `ModuleMap` and `ModulePage`
  were implemented to spec, but the card-level navigation was never wired; only the Continue
  button received `onClick → navigate`.

### Source files traced
- `web/src/features/module/ModulePage.tsx` — full file (lines 1–130)
- `web/src/features/module/ModuleMap.tsx` — full file (lines 1–99)
- `web/src/features/module/module.api.ts` — full file
- `web/src/features/module/module.types.ts` — full file
- `web/src/components/Card.tsx` — full file
- `web/src/components/Card.module.css` — full file
- `web/src/features/module/ModulePage.test.tsx` — full file (confirms no test for post-Finish navigation)
- `web/src/features/module/ModuleMap.test.tsx` — full file (confirms the "no link" test)
- `web/src/features/staff/StaffVideosPage.tsx` — read for house-style Card + navigation patterns

### Verification
Code tracing was sufficient to confirm both root causes with certainty. No runtime execution was
required because the logic is explicit in the source and the tests themselves document the
broken behaviour (particularly `ModuleMap.test.tsx` line 102–107, which asserts no `<a>` wraps
the open card).

---

## Bug 1 — "Finish module" does nothing visible

### Root Cause

**File:** `web/src/features/module/ModulePage.tsx`

The "Finish module" / "Next →" button always calls `handleNext()` (line 66), which calls
`navigateTo(currentIndex + 1)` (line 57):

```tsx
// ModulePage.tsx line 50–55
function navigateTo(newIndex: number) {
  const clamped = Math.max(0, Math.min(newIndex, segments.length - 1))
  setSegmentIndex(clamped)
  // …
  mutation.mutate(segments[clamped].position)
}
```

When the student is on the **last segment**, `currentIndex === segments.length - 1`.
`navigateTo(currentIndex + 1)` computes:

```
clamped = Math.min(currentIndex + 1, segments.length - 1)
        = Math.min(segments.length, segments.length - 1)
        = segments.length - 1
        = currentIndex          ← same index as before
```

So `setSegmentIndex(clamped)` sets the state to the **same value it already holds** — React sees
no state change and does not re-render. The `mutation.mutate(...)` call fires and correctly marks
the module complete on the backend (the backend's `save_position` sets `status = 'complete'` and
records `completed_at` when `segment_position >= last_index`), but:

1. **No navigation occurs** — `navigateTo` never calls `navigate('/')` or any router function.
2. **No completion UI appears** — `onSuccess` only invalidates TanStack Query caches
   (lines 20–23), it does not set any local "completed" state or show a banner.
3. **The student sees no change** — they are still on the last segment page. The button briefly
   enters `loading` state while the mutation is in-flight, then returns to "Finish module". To the
   student it looks like nothing happened.

### Exact Line References

| Location | Line(s) | Code |
|---|---|---|
| `handleNext` definition | `ModulePage.tsx:63–65` | `function handleNext() { navigateTo(currentIndex + 1) }` |
| `navigateTo` — the clamp | `ModulePage.tsx:51` | `const clamped = Math.max(0, Math.min(newIndex, segments.length - 1))` |
| `navigateTo` — state set | `ModulePage.tsx:52` | `setSegmentIndex(clamped)` ← no-op when already on last segment |
| `mutation.onSuccess` | `ModulePage.tsx:20–23` | invalidates queries only; no navigation, no banner |
| "Finish module" button | `ModulePage.tsx:118–125` | renders `isLast ? 'Finish module' : 'Next →'`; `onClick={handleNext}` |

### Current Behaviour
Student clicks "Finish module". Button goes into loading state for ~200ms. Backend marks module
complete. Query caches are invalidated. Button returns to "Finish module". Page is unchanged.
Student has no idea the module is complete.

### Intended Behaviour / Recommended Fix Direction

After the mutation succeeds **and** `isLast` is true, navigate back to the module map (`'/'`).
The map will reload from the invalidated cache and show the module as `complete`, and the next
module (if any) will show as `open`.

The fix lives in the `mutation.onSuccess` callback. `isLast` must be captured by the handler
(it is available in closure scope, or the position can be compared to `segments.length - 1`).
A completion banner is optional but recommended in addition to navigation (or instead of it, per
UX preference).

Minimal fix shape (do not implement — diagnosis only):

```tsx
const mutation = useMutation({
  mutationFn: (position: number) => savePosition(id, position),
  onSuccess: (_data, position) => {
    void queryClient.invalidateQueries({ queryKey: ['modules'] })
    void queryClient.invalidateQueries({ queryKey: ['module', id] })
    // Navigate home after finishing the last segment
    if (position === segments[segments.length - 1].position) {
      void navigate('/')
    }
  },
})
```

`useNavigate` is already imported from react-router in the file tree; it just needs to be called
inside `ModulePage` and threaded into the mutation.

Note: `navigate` is currently not imported or called anywhere in `ModulePage.tsx`. It IS imported
and used in `ModuleMap.tsx` (line 3: `import { useNavigate } from 'react-router'`), so the
pattern is established in the codebase.

---

## Bug 2 — Module map cards are not clickable / do not navigate

### Root Cause

**File:** `web/src/features/module/ModuleMap.tsx`

The `ModuleRow` component (lines 29–53) renders a `<Card>` with `interactive={!isLocked}` but
**never wraps it in a `<Link>` and never attaches an `onClick` handler to the card itself**:

```tsx
// ModuleMap.tsx lines 35–52
return (
  <li>
    <Card interactive={!isLocked} className={`${styles.row} ${isLocked ? styles.locked : ''}`}>
      {/* … module number, title, progress bar, duration, tag … */}
    </Card>
  </li>
)
```

The `Card` component (`web/src/components/Card.tsx`) is a plain `<div>`:

```tsx
// Card.tsx lines 1–12
export function Card({ interactive = false, className, ...rest }: CardProps) {
  const classes = [styles.card, interactive && styles.interactive, className]
    .filter(Boolean)
    .join(' ')
  return <div className={classes} {...rest} />
}
```

`interactive` is **CSS-only** — it applies a hover lift animation (border-color + translateY via
`Card.module.css:.interactive`). It does **not** make the card a focusable element, does not add
a keyboard handler, and does not wire any navigation. The `CardProps` type
(`HTMLAttributes<HTMLDivElement> & { interactive?: boolean }`) accepts `onClick` via spread
(`...rest`), but `ModuleRow` does not pass one.

The only navigation on the map is in the `ModuleMap` component itself (lines 87–93):

```tsx
// ModuleMap.tsx lines 87–93
{continueTarget && (
  <div className={styles.continueBar}>
    <Button variant="primary" onClick={() => void navigate(`/modules/${continueTarget.id}`)}>
      Continue module {continueTarget.number} →
    </Button>
  </div>
)}
```

`continueTarget` is the first `in_progress` module, or the first `open` module (line 57–59).
There is exactly one Continue button, targeting one module. No other navigation is wired.

The existing test `ModuleMap.test.tsx:102–107` explicitly documents and asserts this broken state:

```tsx
// ModuleMap.test.tsx lines 96–107
it('open module card is not wrapped in an anchor either (uses navigate button)', async () => {
  // The module map uses a Continue button and Card (not per-card links), so no <a> per row.
  moduleListApi([openModule])
  renderApp('/')
  await screen.findByText('Warm-up and queue refresher')
  // No link to the module page from the card itself — navigation is via Continue button
  expect(screen.queryByRole('link', { name: /warm-up/i })).toBeNull()
})
```

This test was written to document the current behaviour, not to verify correct behaviour. It will
need to be inverted / replaced when the fix is applied.

### Exact Line References

| Location | Line(s) | Code / significance |
|---|---|---|
| `ModuleRow` render — Card with no onClick/Link | `ModuleMap.tsx:35–52` | `<Card interactive={!isLocked}>` — no navigation wired |
| `Card` component definition | `Card.tsx:6–11` | renders a `<div>`; `interactive` is CSS only |
| `Card.module.css:.interactive` | `Card.module.css:9–17` | hover lift — purely visual, no interaction semantics |
| Only navigation on the map | `ModuleMap.tsx:87–93` | `<Button onClick={() => navigate(...)}>` — single Continue button |
| `findContinueTarget` | `ModuleMap.tsx:57–59` | picks first `in_progress` else first `open` — only ONE module navigable |
| Documenting test | `ModuleMap.test.tsx:96–107` | asserts no link on card — must be updated when fix lands |

### Current Behaviour
Clicking anywhere on an open, in-progress, or complete module card does nothing. Only the
"Continue module N →" button navigates, and it targets only one module (the in-progress or first
open one). A student who wants to revisit a complete module or jump to a specific open module
cannot do so by clicking the card.

### Intended Behaviour / Recommended Fix Direction

For `open`, `in_progress`, and `complete` modules: wrap the `<Card>` in a `<Link to={/modules/${module.id}}>` from react-router, or add `onClick={() => void navigate(...)}` to the card.
For `locked` modules: leave non-interactive (no link, no handler).

**House style:** `StaffVideosPage.tsx` uses `<Card>` with a `<Link>` **inside** the card
(the title is the link, line 21–23). That pattern puts the link on a text node, not on the whole
card. For the module map the whole card surface should be the tap target, so the appropriate
pattern is to wrap the `Card` in a `<Link>`:

```tsx
// Diagnosis-only sketch — do not implement as-is
<li>
  {isLocked ? (
    <Card className={`${styles.row} ${styles.locked}`}>…</Card>
  ) : (
    <Link to={`/modules/${module.id}`}>
      <Card interactive className={styles.row}>…</Card>
    </Link>
  )}
</li>
```

Alternatively, `Card` can be extended to accept an `as` prop or `href`, but the simpler and more
house-consistent approach is to wrap with `<Link>`. The `Card.tsx` type already accepts `onClick`
via `HTMLAttributes<HTMLDivElement>` spread, so passing `onClick` directly to the card (instead
of wrapping in a Link) is also viable, but `<Link>` is preferred for keyboard / accessibility
(native anchor semantics, right-click → "Open in new tab", etc.).

The test in `ModuleMap.test.tsx:96–107` that currently asserts `queryByRole('link', ...) → null`
must be updated (or replaced with a test that asserts the link IS present for open modules and
IS absent for locked modules).

The Continue button can remain — it is a useful quick-action for resuming. It is not a
replacement for per-card navigation.

---

## Affected Files

| File | Lines to modify |
|---|---|
| `web/src/features/module/ModulePage.tsx` | Lines 18–23 (`mutation` definition — add `onSuccess` navigation); add `useNavigate` call (~line 10 area) |
| `web/src/features/module/ModuleMap.tsx` | Lines 29–52 (`ModuleRow` render — wrap Card in Link for non-locked modules) |
| `web/src/features/module/ModuleMap.test.tsx` | Lines 96–107 (update/replace the "no link" assertion to reflect correct behaviour) |

No backend changes are needed. The backend already correctly marks the module complete and unlocks
the next module; the bugs are purely frontend UX.

---

## Summary

**Bug 1:** `navigateTo` clamps `currentIndex + 1` to `segments.length - 1`, so on the last
segment the call is a no-op for navigation — `setSegmentIndex` receives the same value it already
holds. The mutation fires and the backend marks the module complete, but `onSuccess` only
invalidates caches; it never calls `navigate('/')`. The student sees nothing happen.
Fix: call `navigate('/')` in `onSuccess` when the saved position equals the last segment's
position.

**Bug 2:** `ModuleRow` renders `<Card interactive={!isLocked}>` which applies a CSS hover effect
but is a plain `<div>` with no `onClick` or `<Link>` wrapper. Navigation is only wired to the
single "Continue" button in `ModuleMap`. Open, in-progress, and complete module cards are visually
interactive (hover lift) but functionally inert.
Fix: wrap the `<Card>` in a `<Link to={/modules/${module.id}}>` for non-locked modules.
