import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Alert, Button, Card, Spinner, Tag } from '../../components'
import { usePageTitle } from '../../pages/usePageTitle.ts'
import { useRefreshRewards } from '../rewards/hooks.ts'
import { fetchModules, fetchQuickCheck, takeQuickCheck } from './module.api.ts'
import type { ModuleSummary, QuickCheckQuestion, QuickCheckResult } from './module.types.ts'

/** /modules/:moduleId/check — "Already know this?": a module's quick check (FR-8.2, #214).
 *
 * Four questions on one page, one answer each, no hints, marked together at the end. At most one
 * wrong passes: the module is marked tested out and the student moves on. Otherwise the result
 * names what was missed and suggests where to start; nothing is taken away or locked. One try per
 * module, so a student who has taken it sees the result again here. */
export function QuickCheckPage() {
  const id = Number(useParams().moduleId)
  const queryClient = useQueryClient()
  const check = useQuery({ queryKey: ['quick-check', id], queryFn: () => fetchQuickCheck(id) })
  const modules = useQuery({ queryKey: ['modules'], queryFn: fetchModules })
  const refreshRewards = useRefreshRewards()
  // Set at once, so a second press that lands before React re-renders the busy button doesn't
  // send the answers twice (#215 review); the API refuses a second send too.
  const inFlight = useRef(false)
  const mutation = useMutation({
    mutationFn: (answers: { activityId: number; selected: string }[]) =>
      takeQuickCheck(id, answers),
    onSettled: () => {
      inFlight.current = false
    },
    onSuccess: (result) => {
      queryClient.setQueryData(['quick-check', id], {
        ...check.data,
        available: false,
        questions: [],
        result,
      })
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      void queryClient.invalidateQueries({ queryKey: ['module', id] })
      // A pass gives the module its medal at once, not after the skills' 30 s (#215 review).
      refreshRewards()
    },
  })
  const module = modules.data?.find((m) => m.id === id)
  usePageTitle(module && `Quick check: module ${module.number}, ${module.title}`)

  if (check.isPending) return <Spinner label="Loading the quick check" />
  if (check.isError)
    return (
      <section className="grid justify-items-start gap-3">
        <h1 className="text-2xl font-bold">This module has no quick check</h1>
        <Alert tone="info">{check.error.message}</Alert>
        <BackToModules />
      </section>
    )

  const name = module ? `Module ${module.number} · ${module.title}` : `Module ${id}`
  const result = check.data.result

  return (
    <section className="mx-auto grid w-full max-w-3xl gap-6" aria-label={`${name}: quick check`}>
      <Link
        to="/"
        className="inline-flex min-h-11 items-center justify-self-start text-sm text-muted-foreground hover:text-foreground"
      >
        ← All modules
      </Link>
      {result ? (
        <Result result={result} name={name} moduleId={id} modules={modules.data ?? []} />
      ) : !check.data.available ? (
        <>
          <h1 className="text-2xl font-bold">{name}: quick check</h1>
          <Alert tone="info">
            You have completed this module already, so you don’t need its quick check.
          </Alert>
          <BackToModules />
        </>
      ) : (
        <Questions
          name={name}
          moduleId={id}
          passMark={check.data.passMark}
          questions={check.data.questions}
          submitting={mutation.isPending}
          error={mutation.isError ? mutation.error.message : undefined}
          onSubmit={(answers) => {
            if (inFlight.current || mutation.isPending) return
            inFlight.current = true
            mutation.mutate(answers)
          }}
        />
      )}
    </section>
  )
}

function BackToModules() {
  return (
    <Link to="/" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
      Back to your modules
    </Link>
  )
}

function Questions({
  name,
  moduleId,
  passMark,
  questions,
  submitting,
  error,
  onSubmit,
}: {
  name: string
  moduleId: number
  passMark: number
  questions: QuickCheckQuestion[]
  submitting: boolean
  error: string | undefined
  onSubmit: (answers: { activityId: number; selected: string }[]) => void
}) {
  const [chosen, setChosen] = useState<Record<number, string>>({})
  const [missing, setMissing] = useState<number[]>([])
  return (
    <form
      className="grid gap-6"
      onSubmit={(event) => {
        event.preventDefault()
        const unanswered = questions.flatMap((q, index) => (chosen[q.id] ? [] : [index + 1]))
        setMissing(unanswered)
        if (unanswered.length > 0) return
        onSubmit(questions.map((q) => ({ activityId: q.id, selected: chosen[q.id] })))
      }}
    >
      <div className="grid gap-2">
        <h1 className="text-2xl font-bold">{name}: quick check</h1>
        <p className="m-0 text-muted-foreground">
          Already know this module? Answer these {questions.length} questions. There are no hints,
          and you see how you did at the end. Get at least {passMark} right and the module counts as
          done, so you can move on. You get one try.{' '}
          <Link to={`/modules/${moduleId}`}>Work through the module instead</Link>.
        </p>
      </div>
      {questions.map((question, index) => (
        <Card key={question.id}>
          <fieldset className="m-0 grid gap-2 border-0 p-0">
            <legend className="mb-2 font-medium">
              <span className="block text-sm text-muted-foreground">
                Question {index + 1} of {questions.length}
              </span>
              {question.prompt}
            </legend>
            {question.options.map((option) => (
              <label
                key={option.id}
                className="flex cursor-pointer items-start gap-3 rounded border border-border p-3 has-[:checked]:border-primary"
              >
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option.id}
                  checked={chosen[question.id] === option.id}
                  className="mt-1"
                  onChange={() => {
                    setChosen((now) => ({ ...now, [question.id]: option.id }))
                    setMissing((now) => now.filter((n) => n !== index + 1))
                  }}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </fieldset>
        </Card>
      ))}
      {missing.length > 0 && (
        <p className="m-0 text-sm text-warning" role="alert">
          Answer every question first: {missing.length === 1 ? 'question' : 'questions'}{' '}
          {missing.join(', ')} {missing.length === 1 ? 'has' : 'have'} no answer yet.
        </p>
      )}
      {error && (
        <Alert tone="danger" title="Your answers could not be checked">
          {error}
        </Alert>
      )}
      <div>
        <Button type="submit" variant="primary" loading={submitting} keepFocusWhileLoading>
          Check my answers
        </Button>
      </div>
    </form>
  )
}

function moduleName(modules: ModuleSummary[], id: number | null): string {
  const found = modules.find((m) => m.id === id)
  return found ? `module ${found.number}: ${found.title}` : `module ${id}`
}

function Result({
  result,
  name,
  moduleId,
  modules,
}: {
  result: QuickCheckResult
  name: string
  moduleId: number
  modules: ModuleSummary[]
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => heading.current?.focus(), [])
  const here = modules.find((m) => m.id === moduleId)
  const suggested = result.suggestedModule
  return (
    <div className="grid gap-6">
      <h1 ref={heading} tabIndex={-1} className="text-2xl font-bold">
        {name}: quick check, {result.correct} of {result.total} right
      </h1>
      {result.passed ? (
        <Alert tone="success" title="You know this already">
          Module {here?.number ?? moduleId} counts as done: you passed its quick check. It stays
          open if you want to look through it.
          {result.lookAt.length > 0 && ` Worth a second look: ${result.lookAt.join(', ')}.`}
        </Alert>
      ) : (
        <Alert tone="info" title="Not enough to skip this one, and that’s fine">
          Now you know what to look at: {result.lookAt.join(', ')}.{' '}
          {result.suggestion === 'start_with'
            ? `Start with ${moduleName(modules, suggested)}, which builds what this module needs.`
            : 'Work through this module: it teaches exactly these.'}
        </Alert>
      )}
      <div className="flex flex-wrap gap-3">
        {result.passed ? (
          suggested !== null ? (
            <Link to={`/modules/${suggested}`} className={buttonVariants({ variant: 'default' })}>
              Go to {moduleName(modules, suggested)} →
            </Link>
          ) : (
            <Link to="/" className={buttonVariants({ variant: 'default' })}>
              Back to your modules →
            </Link>
          )
        ) : result.suggestion === 'start_with' ? (
          <>
            <Link to={`/modules/${suggested}`} className={buttonVariants({ variant: 'default' })}>
              Start with module {modules.find((m) => m.id === suggested)?.number ?? suggested} →
            </Link>
            <Link to={`/modules/${moduleId}`} className={buttonVariants({ variant: 'outline' })}>
              Work through this module
            </Link>
          </>
        ) : (
          <Link to={`/modules/${moduleId}`} className={buttonVariants({ variant: 'default' })}>
            Work through this module →
          </Link>
        )}
      </div>
      <section aria-labelledby="quick-check-answers" className="grid gap-3">
        <h2 id="quick-check-answers" className="m-0 text-lg font-semibold">
          Your answers
        </h2>
        {result.items.map((item, index) => (
          <Card key={item.activityId}>
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="m-0 font-semibold">
                  {index + 1}. {item.title}
                </h3>
                <Tag tone={item.correct ? 'success' : 'warning'} icon={item.correct ? '✓' : '○'}>
                  {item.correct ? 'right' : 'to look at'}
                </Tag>
              </div>
              <p className="m-0">{item.prompt}</p>
              <p className="m-0 text-sm">Your answer: {item.chosen}</p>
              {!item.correct && <p className="m-0 text-sm">The answer: {item.answer}</p>}
              <p className="m-0 text-sm text-muted-foreground">{item.explanation}</p>
            </div>
          </Card>
        ))}
      </section>
    </div>
  )
}
