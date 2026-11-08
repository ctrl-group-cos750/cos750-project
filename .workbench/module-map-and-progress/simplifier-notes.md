## Simplifier Notes — module-map-and-progress

### Files Modified

- `api/app/services/modules.py` — extracted duplicate prev-complete logic; removed TODO duplication
- `web/src/features/module/ModuleMap.tsx` — removed intermediate variable; prettier re-formatted
- `web/src/features/module/ModulePage.tsx` — simplified redundant `disabled` condition
- `web/src/features/module/SegmentView.tsx` — removed redundant `kind` variable; removed unused import

### Significant Changes

#### `api/app/services/modules.py`

**Extracted `_is_prev_complete_for_user` helper.**
Both `get_module_detail` and `save_position` contained an identical 10-line inline block that
fetched the previous module by number and checked its progress status.  That block was extracted
into a new private helper `_is_prev_complete_for_user(session, module, user_id) -> bool`.

Before (duplicated in both functions):
```python
prev_done = False
if module.number > 0:
    prev_module = session.scalar(select(Module).where(Module.number == module.number - 1))
    if prev_module is not None:
        prev_progress = session.scalar(
            select(ModuleProgress).where(
                ModuleProgress.user_id == user_id,
                ModuleProgress.module_id == prev_module.id,
            )
        )
        prev_done = prev_progress is not None and prev_progress.status == "complete"
```

After (single call in each):
```python
prev_done = _is_prev_complete_for_user(session, module, user_id)
```

The existing `_prev_module_complete` helper (which takes pre-fetched dicts) is unchanged and
still used by the bulk `get_modules_for_user` path.

**Removed duplicate TODO comment.**  The `save_position` docstring contained the same
"Gate completion on required activities" TODO that was already present as an inline comment.
The duplicate in the docstring was removed; the inline comment remains.

#### `web/src/features/module/ModuleMap.tsx`

**Removed `isInteractive` intermediate.**  `isInteractive = !isLocked` was only ever used in
one place as `interactive={isInteractive}`.  Changed to `interactive={!isLocked}` directly,
which is immediately readable.  Prettier collapsed the short `Card` prop line as a side-effect.

#### `web/src/features/module/ModulePage.tsx`

**Simplified redundant `disabled` condition.**  The Next button had:
```tsx
disabled={(isLast && mutation.isPending) || mutation.isPending}
```
`(isLast && X) || X` always equals `X`, so this reduces to:
```tsx
disabled={mutation.isPending}
```
Behaviour is unchanged: the button is disabled while a save is in flight.

#### `web/src/features/module/SegmentView.tsx`

**Removed redundant `kind` variable.**  `const kind: SegmentKind = segment.kind` was assigned
only to be used as the `switch` expression.  Changed the `switch` to dispatch directly on
`segment.kind`.  The exhaustiveness check in the `default` branch also updated to use
`segment.kind`, and the now-unused `SegmentKind` type import was removed.

### Build Verification

`scripts/check.sh` exits 0 after all changes:

```
== web
All matched files use Prettier code style!
Found 0 warnings and 0 errors.        (oxlint, 67 files)
Test Files: 12 passed (12)
Tests:      131 passed (131)           ← unchanged from pre-simplification
tsc -b + vite build ✓

== api
64 files already formatted
All checks passed!                     (ruff)
Success: no issues found in 56 source files  (mypy strict)
435 passed, 1 skipped                  ← unchanged from pre-simplification

== all checks passed
```
