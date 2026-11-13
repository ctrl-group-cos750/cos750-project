import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { AttemptResult } from '../activities/activities.types.ts'
import { CelebrationAllowed } from '../activities/celebration.ts'
import { FeedbackPanel } from '../activities/FeedbackPanel.tsx'
import { praiseFor } from '../progress/praise.ts'
import { setPreferenceOwner, storedCompanion } from '../progress/preferences.ts'
import { CompanionAnnouncer } from './Companion.tsx'
import {
  answerLine,
  moduleDoneLine,
  quickCheckLine,
  resetStreak,
  rightLine,
  wrongLine,
} from './companion.ts'

let nextId = 1
function result(correct: boolean, more: Partial<AttemptResult> = {}): AttemptResult {
  return {
    id: nextId++,
    activityId: 7,
    correct,
    score: correct ? 1 : 0,
    parts: [],
    feedback: correct
      ? 'D joined the queue before E. So D comes out first.'
      : 'Not quite: look at the queue.',
    hintLevel: 0,
    ...more,
  }
}

/** A feedback panel the test can give new results to, as answers are checked. */
function panel({ allowed = true } = {}) {
  const client = new QueryClient()
  client.setQueryData(['rewards'], { hideRewards: false, points: 0, badges: [] })
  const view = (r: AttemptResult | undefined) => (
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <CelebrationAllowed.Provider value={allowed}>
          <FeedbackPanel result={r} />
        </CelebrationAllowed.Provider>
        <CompanionAnnouncer />
      </QueryClientProvider>
    </MemoryRouter>
  )
  const { rerender } = render(view(undefined))
  return (r: AttemptResult | undefined) => rerender(view(r))
}

const announced = () => document.querySelector('[data-companion-announcer]')?.textContent ?? ''

beforeEach(() => {
  localStorage.clear()
  setPreferenceOwner(1)
  resetStreak()
})

describe('the study companion (#214)', () => {
  it('asks once, after the first answer checked, and remembers "No thanks"', async () => {
    const show = panel()
    show(result(true))
    expect(
      screen.getByText('Want a study companion? Inka can comment on your answers.'),
    ).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'No thanks' }))
    expect(screen.queryByText(/Want a study companion/)).toBeNull()
    expect(storedCompanion()).toBe('off')
    show(result(false))
    expect(screen.queryByText(/Want a study companion/)).toBeNull()
    expect(document.querySelector('[data-companion]')).toBeNull()
  })

  it('does not ask again when the question was ignored', () => {
    const show = panel()
    show(result(true))
    expect(screen.getByText(/Want a study companion/)).toBeVisible()
    show(result(true))
    expect(screen.queryByText(/Want a study companion/)).toBeNull()
  })

  it('"Yes" brings Inka, the default, who speaks about this answer at once', async () => {
    const show = panel()
    show(result(true))
    await userEvent.click(screen.getByRole('button', { name: 'Yes' }))
    expect(storedCompanion()).toBe('inka')
    const companion = document.querySelector('[data-companion="inka"]') as HTMLElement
    expect(companion).not.toBeNull()
    expect(within(companion).getByText('Right: D joined the queue before E.')).toBeVisible()
    expect(announced()).toBe('Inka: Right: D joined the queue before E.')
    // Its line replaces the varied line under a right answer: said once, not twice.
    show(result(true, { id: 500 }))
    expect(screen.queryByText(praiseFor(500, 0))).toBeNull()
  })

  it('points a wrong answer at the next hint', () => {
    localStorage.setItem('ctrl-academy.1.companion', 'rook')
    const show = panel()
    show(result(false, { hintLevel: 1 }))
    const companion = document.querySelector('[data-companion="rook"]') as HTMLElement
    expect(
      within(companion).getByText('Not yet. Hint 2 gives the rule for this one.'),
    ).toBeVisible()
    expect(announced()).toBe('Rook: Not yet. Hint 2 gives the rule for this one.')
  })

  it('is never in the mastery check', () => {
    localStorage.setItem('ctrl-academy.1.companion', 'inka')
    const show = panel({ allowed: false })
    show(result(true))
    expect(document.querySelector('[data-companion]')).toBeNull()
    expect(screen.queryByText(/Want a study companion/)).toBeNull()
    // Nor on a withheld mastery answer anywhere.
    show(result(true, { correct: null, withheld: true }))
    expect(document.querySelector('[data-companion]')).toBeNull()
  })

  it('turns off from its own menu, with Undo', async () => {
    localStorage.setItem('ctrl-academy.1.companion', 'juno')
    const show = panel()
    show(result(true))
    await userEvent.click(screen.getByRole('button', { name: 'Juno: companion options' }))
    await userEvent.click(screen.getByRole('button', { name: 'Turn off companion' }))
    expect(storedCompanion()).toBe('off')
    expect(screen.getByText(/Study companion off\./)).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(storedCompanion()).toBe('juno')
  })

  it('is chosen in the profile: the five by name, and Off', async () => {
    fakeApi({ user: ada })
    renderApp('/profile')
    const group = await screen.findByRole('group', { name: 'Study companion' })
    expect(
      within(group)
        .getAllByRole('radio')
        .map((r) => r.getAttribute('value')),
    ).toEqual(['inka', 'rowan', 'juno', 'sol', 'rook', 'off'])
    expect(within(group).getByRole('radio', { name: 'Off' })).toBeChecked()
    await userEvent.click(within(group).getByRole('radio', { name: 'Sol' }))
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.companion`)).toBe('sol')
  })
})

describe('what the companion says', () => {
  it('says why a right answer is right, from the explanation', () => {
    expect(rightLine('Ama joined first. So she leaves first.')).toBe('Right: Ama joined first.')
    expect(rightLine('Correct.')).toBe('Right.')
  })

  it('names what to check on a near miss, and the next hint otherwise', () => {
    const parts = [
      { ref: 0, correct: true, message: null },
      { ref: 1, correct: true, message: null },
      { ref: 2, correct: false, message: null },
    ]
    expect(wrongLine(parts, 0)).toBe('2 of 3 right. Check the one marked, the rest can stay.')
    expect(wrongLine([], 0)).toBe('Not yet. Hint 1 points at where to look.')
    expect(wrongLine([], 2)).toBe('Hint 3 walks through it step by step, then try once more.')
    expect(wrongLine([], 4)).toMatch(/last hint/)
  })

  it('never praises the person and never exclaims', () => {
    const lines = [
      rightLine('Because the queue is first in, first out.'),
      wrongLine([], 0),
      wrongLine([], 3),
      quickCheckLine(2, 3, 4, [{ title: 'When BFS fits' }]).text,
      moduleDoneLine(2, ['Map Maker']).text,
    ]
    for (const line of lines) {
      expect(line).not.toMatch(/!|smart|genius|clever|great job|amazing/i)
    }
  })

  it('says less after three right in a row: only the pose changes', () => {
    const right = () => answerLine(result(true))
    expect([right(), right(), right()].every((l) => l.text !== null)).toBe(true)
    const quiet = right()
    expect(quiet).toEqual({ pose: 'pleased', text: null })
    expect(answerLine(result(false)).text).not.toBeNull() // a wrong answer always gets its pointer
  })

  it('sums up a quick check and a finished module', () => {
    expect(quickCheckLine(2, 4, 4, []).text).toBe('4 of 4. Module 2 is tested out.')
    expect(quickCheckLine(3, 3, 4, [{ title: 'When BFS fits' }]).text).toBe(
      '3 of 4. Look again at the one on when BFS fits: it finds the fewest edges, not the cheapest route.',
    )
    expect(moduleDoneLine(2, ['Map Maker']).text).toBe('Module 2 done. Map Maker is now secure.')
    expect(moduleDoneLine(1, ['Word Smith', 'Map Maker']).text).toBe(
      'Module 1 done. Word Smith and Map Maker are now secure.',
    )
  })
})
