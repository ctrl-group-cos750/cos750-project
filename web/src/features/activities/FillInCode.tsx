import { useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, FillInActivity } from './activities.types.ts'

type FillInCodeProps = {
  activity: FillInActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (answers: Record<number, string>) => Promise<void>
}

const PYTHON_TOKEN =
  /(#[^\n]*|"[^"\n]*"|'[^'\n]*'|\b(?:def|return|for|in|while|if|else|elif|import|from|class|True|False|None|and|or|not)\b|\b\d+\b)/g
const BLANK = /__(\d+)__/g

function HighlightedText({ text }: { text: string }) {
  const parts = text.split(PYTHON_TOKEN)
  const occurrences = new Map<string, number>()
  return parts.map((part) => {
    if (!part) return null
    const occurrence = occurrences.get(part) ?? 0
    occurrences.set(part, occurrence + 1)
    const className = part.startsWith('#')
      ? 'text-muted-foreground'
      : /^(?:"|')/.test(part)
        ? 'text-success'
        : /^\d+$/.test(part)
          ? 'text-warning'
          : /^(?:def|return|for|in|while|if|else|elif|import|from|class|True|False|None|and|or|not)$/.test(
                part,
              )
            ? 'font-semibold text-primary'
            : undefined
    return (
      <span key={`${part}-${occurrence}`} className={className}>
        {part}
      </span>
    )
  })
}

/** Read-only highlighted Python with token-only blank controls; no free-form code can be entered. */
export function FillInCode({ activity, result, submitting, onSubmit }: FillInCodeProps) {
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const disabled = submitting || result?.correct === true
  const partsByBlank = new Map(result?.parts.map((part) => [part.ref, part]))
  const lineOccurrences = new Map<string, number>()

  function renderLine(line: string) {
    const pieces: React.ReactNode[] = []
    let cursor = 0
    for (const match of line.matchAll(BLANK)) {
      const [whole, idText] = match
      const blankId = Number(idText)
      pieces.push(<HighlightedText key={`text-${cursor}`} text={line.slice(cursor, match.index)} />)
      const part = partsByBlank.get(blankId)
      pieces.push(
        <select
          key={`blank-${blankId}`}
          aria-label={`Blank ${blankId}`}
          value={answers[blankId] ?? ''}
          disabled={disabled}
          className={`mx-1 rounded border bg-background px-1 py-0.5 font-mono text-sm ${part ? (part.correct ? 'border-success' : 'border-warning') : 'border-primary'}`}
          onChange={(event) =>
            setAnswers((current) => ({ ...current, [blankId]: event.target.value }))
          }
        >
          <option value="">blank {blankId}</option>
          {activity.config.options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>,
      )
      cursor = (match.index ?? 0) + whole.length
    }
    pieces.push(<HighlightedText key="remainder" text={line.slice(cursor)} />)
    return pieces
  }

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit(answers)
      }}
    >
      {/* The code keeps its indentation (whitespace-pre): in Python it is the program, and the
          student has to see what sits inside the loop (#140). A line wider than the screen
          scrolls inside this region instead of wrapping or widening the page (WCAG 1.4.10); the
          region is focusable and named so a keyboard user can scroll it too. */}
      <section
        className="min-w-0 overflow-x-auto rounded border bg-muted/40 p-3 font-mono text-sm leading-7"
        aria-label="Python code with blanks"
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scroll container must be reachable by keyboard (WCAG 2.1.1)
        tabIndex={0}
      >
        {activity.config.code.split('\n').map((line, index) => {
          const occurrence = lineOccurrences.get(line) ?? 0
          lineOccurrences.set(line, occurrence + 1)
          return (
            <div key={`${line}-${occurrence}`} className="grid w-max grid-cols-[2.5rem_1fr]">
              <span
                aria-hidden="true"
                className="select-none pr-3 text-right text-muted-foreground"
              >
                {index + 1}
              </span>
              <code className="whitespace-pre">{renderLine(line)}</code>
            </div>
          )
        })}
      </section>
      {result && (
        <ul className="m-0 grid list-none gap-2 p-0" aria-label="Result for each blank">
          {activity.config.blanks.map((blankId) => {
            const part = partsByBlank.get(blankId)
            return part ? (
              <li key={blankId} className={part.correct ? 'text-success' : 'text-warning'}>
                {part.correct ? 'Correct' : 'Check again'}: blank {blankId}
                {part.message && ` — ${part.message}`}
              </li>
            ) : null
          })}
        </ul>
      )}
      <div>
        <Button type="submit" loading={submitting} disabled={disabled}>
          Check answer
        </Button>
      </div>
    </form>
  )
}
