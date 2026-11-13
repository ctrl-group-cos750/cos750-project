import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { AttemptResult } from '../activities/activities.types.ts'
import { CelebrationAllowed } from '../activities/celebration.ts'
import { FeedbackPanel } from '../activities/FeedbackPanel.tsx'
import { praiseFor } from '../progress/praise.ts'
import { setPreferenceOwner, storedCompanion } from '../progress/preferences.ts'
import { CompanionAnnouncer, PROMPT_SEEN_MS } from './Companion.tsx'
import {
  answerLine,
  moduleDoneLine,
  quickCheckLine,
  resetStreak,
  RIGHT_AFTER_WRONG,
  rightLine,
  wrongLine,
} from './companion.ts'
import module1 from '../../../../api/app/seed/module-1.json'
import module2 from '../../../../api/app/seed/module-2.json'
import module3 from '../../../../api/app/seed/module-3.json'
import module4 from '../../../../api/app/seed/module-4.json'
import module5 from '../../../../api/app/seed/module-5.json'

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

const prompt = () => document.querySelector<HTMLElement>('[data-companion-prompt]')
const announced = () => document.querySelector('[data-companion-announcer]')?.textContent ?? ''

beforeEach(() => {
  localStorage.clear()
  setPreferenceOwner(1)
  resetStreak()
})

afterEach(() => {
  vi.restoreAllMocks()
})

/** The result the feedback panel focuses. */
const resultGroup = () =>
  document.querySelector('section[aria-label="Submission results"] [tabindex="-1"]')

describe('the study companion (#214)', () => {
  it('asks once, after the first answer checked, and remembers "No thanks"', async () => {
    const show = panel()
    show(result(true))
    expect(prompt()).toHaveTextContent('Want a study companion? Inka can comment on your answers.')
    await userEvent.click(screen.getByRole('button', { name: 'No thanks' }))
    expect(prompt()).toBeNull()
    expect(storedCompanion()).toBe('off')
    // The hidden live region no longer holds a question that has gone (#222 re-review).
    expect(announced()).toBe('')
    show(result(false))
    expect(prompt()).toBeNull()
    expect(document.querySelector('[data-companion]')).toBeNull()
  })

  it('reads the question out, politely, after the result, and says it is kept on this device', () => {
    const show = panel()
    show(result(true))
    expect(announced()).toBe(
      'Want a study companion? Inka can comment on your answers. Yes or No thanks, under the result. Kept on this device.',
    )
    expect(screen.getByText('Your choice is kept on this device.')).toBeVisible()
    expect(resultGroup()).toHaveFocus() // the result keeps focus; the question is not in the way
  })

  it.each(['Yes', 'No thanks'])(
    'moves focus back to the result after %s, never to the page',
    async (name) => {
      const show = panel()
      show(result(true))
      await userEvent.click(screen.getByRole('button', { name }))
      expect(document.activeElement).not.toBe(document.body)
      expect(document.activeElement).toBe(resultGroup())
    },
  )

  it('does not ask again once the question was on screen, and heard, then ignored', () => {
    let now = 1_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => now)
    const show = panel()
    show(result(true))
    expect(prompt()).toBeVisible()
    expect(storedCompanion()).toBeNull() // not decided just by being shown
    now += PROMPT_SEEN_MS
    show(result(true))
    expect(storedCompanion()).toBe('off')
    expect(prompt()).toBeNull()
  })

  it('asks again when the question only flashed by, unanswered', () => {
    let now = 1_000_000
    vi.spyOn(Date, 'now').mockImplementation(() => now)
    const show = panel()
    show(result(true))
    now += 500
    show(result(true))
    expect(storedCompanion()).toBeNull()
    expect(prompt()).toBeVisible()
  })

  it('"Yes" brings Inka, the default, who speaks about this answer at once', async () => {
    const show = panel()
    show(result(true))
    await userEvent.click(screen.getByRole('button', { name: 'Yes' }))
    expect(storedCompanion()).toBe('inka')
    const companion = document.querySelector('[data-companion="inka"]') as HTMLElement
    expect(companion).not.toBeNull()
    // Not the explanation again (the result gives it): how it was reached (#222 review).
    expect(within(companion).getByText('Right, without a hint.')).toBeVisible()
    expect(announced()).toBe('Inka: Right, without a hint.')
    expect(companion.textContent).not.toContain('D joined the queue')
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
    expect(prompt()).toBeNull()
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

  it("is never on a question that decides an objective, such as a review path's fresh items", async () => {
    localStorage.setItem(`ctrl-academy.${ada.id}.companion`, 'inka')
    const fresh = {
      id: 1202,
      kind: 'multiple_choice',
      title: 'Fresh question',
      visible: true,
      purpose: 'mastery',
      config: {
        prompt: 'Which structure does BFS use?',
        options: [
          { id: 'a', label: 'A stack' },
          { id: 'b', label: 'A queue' },
        ],
      },
    }
    const right = { ...result(true), activityId: 1202, points: 10 }
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/1202': () => Response.json(fresh),
        'GET /api/activities/1202/hints': () => Response.json([]),
        'POST /api/activities/1202/attempts': () => Response.json(right, { status: 201 }),
      },
    })
    renderApp('/activities/1202')
    await userEvent.click(await screen.findByRole('radio', { name: 'A queue' }))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(await screen.findByText(/D joined the queue before E/)).toBeVisible()
    expect(document.querySelector('[data-companion]')).toBeNull()
    expect(document.querySelector('[data-companion-prompt]')).toBeNull()
    expect(document.querySelector('[data-success-moment]')).toBeNull()
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
  it('adds to a right answer instead of repeating its explanation', () => {
    expect(rightLine(0)).toBe('Right, without a hint.')
    expect(rightLine(2)).toBe('Right, with hint 2. Try the next one before opening a hint.')
    expect(rightLine(4)).toBe('Right, after the worked steps. Try the next one with fewer hints.')
  })

  it('names what to check on a near miss, and the next hint otherwise', () => {
    const parts = [
      { ref: 0, correct: true, message: null },
      { ref: 1, correct: true, message: null },
      { ref: 2, correct: false, message: null },
    ]
    expect(wrongLine(parts, 0)).toBe('2 of 3 right. Check the one marked, the rest can stay.')
    expect(wrongLine([], 0)).toBe('Not yet. Hint 1 points at where to look.')
    // Never sends a student to hint 3 or 4 without saying it lowers what the answer earns.
    expect(wrongLine([], 2)).toBe(
      'Try once more first if you can. Hint 3 walks through it, but an answer after it counts for less.',
    )
    expect(wrongLine([], 3)).toMatch(
      /^Hint 4 shows a worked answer, and an answer after it counts for less\./,
    )
    expect(wrongLine([], 4)).toMatch(/last hint/)
  })

  it('never praises the person and never exclaims', () => {
    const lines = [
      rightLine(0),
      rightLine(3),
      wrongLine([], 0),
      wrongLine([], 3),
      quickCheckLine(2, 3, 4, [{ activityId: 350, title: 'When BFS fits' }]).text,
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

  it('never says "without a hint" for a right answer after a wrong one, which counts for no medal', () => {
    expect(answerLine(result(false)).pose).toBe('encouraging')
    expect(answerLine(result(true))).toEqual({ pose: 'pleased', text: RIGHT_AFTER_WRONG })
    // Another activity, right at its first attempt, is still right without a hint.
    expect(answerLine(result(true, { activityId: 8 })).text).toBe('Right, without a hint.')
  })

  it('sums up a quick check and a finished module', () => {
    expect(quickCheckLine(2, 4, 4, []).text).toBe("4 of 4. You passed module 2's quick check.")
    expect(quickCheckLine(3, 3, 4, [{ activityId: 350, title: 'When BFS fits' }]).text).toBe(
      '3 of 4. Look again at the one on when BFS fits: BFS follows connections, ring by ring, so look for the job with none to follow.',
    )
    expect(moduleDoneLine(2, ['Map Maker']).text).toBe('Module 2 done. Map Maker is now secure.')
    expect(moduleDoneLine(1, ['Word Smith', 'Map Maker']).text).toBe(
      'Module 1 done. Word Smith and Map Maker are now secure.',
    )
    expect(moduleDoneLine(3, []).text).toBe('Module 3 done.')
  })

  it('has a fitting tip for every quick check item in modules 1 to 5', () => {
    type Item = { id: number; title: string; purpose?: string }
    const items = [module1, module2, module3, module4, module5].flatMap((m) =>
      (m.activities as Item[]).filter((a) => a.purpose === 'test_out'),
    )
    expect(items.length).toBeGreaterThanOrEqual(15)
    for (const item of items) {
      const text = quickCheckLine(1, 3, 4, [{ activityId: item.id, title: item.title }]).text ?? ''
      // Named, so a missing tip says which item: "add_vertex: 3 of 4. Look again at “add_vertex”."
      expect(`${item.title}: ${text}`).toMatch(/: 3 of 4\. Look again at the one on /)
    }
  })
})
