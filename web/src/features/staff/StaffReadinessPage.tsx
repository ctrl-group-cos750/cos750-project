import { useQuery } from '@tanstack/react-query'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Spinner } from '../../components'
import { getReadiness, type Readiness } from './staff.api.ts'

/** One objective's results across the class as a stacked bar, each part also given in words, so
 * the colours are never the only way to read it (NFR-A2). */
function Split({ o, students }: { o: Readiness['objectives'][number]; students: number }) {
  const parts = [
    ['On their own', o.metIndependently, 'bg-success'],
    ['With support', o.metWithSupport, 'bg-primary'],
    ['Not yet', o.notYet, 'bg-warning'],
  ] as const
  const total = Math.max(students, 1)
  return (
    <div className="grid gap-2">
      <div className="flex h-3 overflow-hidden rounded-sm bg-secondary" aria-hidden>
        {parts.map(([label, n, colour]) => (
          <div key={label} className={colour} style={{ width: `${(n / total) * 100}%` }} />
        ))}
      </div>
      <p className="m-0 text-sm text-muted-foreground">
        {parts.map(([label, n]) => `${label}: ${n}`).join(' · ')}
      </p>
    </div>
  )
}

/**
 * /staff/readiness — for the lecturer, before the lecture (Just-in-Time Teaching: Novak et al.,
 * 1999; L10's analytics for teachers). Who is ready, how the class stands on each objective, and
 * the wrong first answers on the mastery items that most students chose, with the content's
 * explanation, so the lecture can start where the class actually is. Counts only, no names.
 */
export function StaffReadinessPage() {
  const query = useQuery({ queryKey: ['staff', 'readiness'], queryFn: getReadiness })
  return (
    <section className="grid gap-6" aria-labelledby="readiness-heading">
      <div className="grid gap-1">
        <h1 id="readiness-heading" className="text-3xl font-semibold">
          Before the lecture
        </h1>
        <p className="text-muted-foreground">
          How the class stands on each objective, from student accounts that have answered the
          mastery check. Open it the morning of the lecture.
        </p>
      </div>
      {query.isPending && <Spinner label="Loading the class's results" />}
      {query.isError && (
        <Alert variant="destructive">
          <AlertDescription>{query.error.message}</AlertDescription>
        </Alert>
      )}
      {query.data && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Card size="sm">
              <CardContent className="grid gap-1">
                <span className="text-muted-foreground">Took the mastery check</span>
                <span className="text-2xl font-semibold tabular-nums">{query.data.students}</span>
              </CardContent>
            </Card>
            <Card size="sm">
              <CardContent className="grid gap-1">
                <span className="text-muted-foreground">Ready for the lecture</span>
                <span className="text-2xl font-semibold tabular-nums">
                  {`${query.data.ready} of ${query.data.students}`}
                </span>
              </CardContent>
            </Card>
          </div>

          <section className="grid gap-3" aria-labelledby="objectives-heading">
            <h2 id="objectives-heading" className="text-xl font-semibold">
              Each objective
            </h2>
            <ol className="m-0 grid list-none gap-4 p-0">
              {query.data.objectives.map((o) => (
                <li key={o.id} className="grid gap-1">
                  <p className="m-0 font-medium">
                    {o.id}. {o.text}
                  </p>
                  <Split o={o} students={query.data.students} />
                </li>
              ))}
            </ol>
          </section>

          <section className="grid gap-3" aria-labelledby="wrong-heading">
            <div className="grid gap-1">
              <h2 id="wrong-heading" className="text-xl font-semibold">
                Wrong answers to address first
              </h2>
              <p className="text-muted-foreground">
                On each mastery question, the wrong option most students chose at their first
                answer, most wrong first.
              </p>
            </div>
            {query.data.commonWrongAnswers.length === 0 ? (
              <p className="text-muted-foreground">No wrong answers on the mastery check yet.</p>
            ) : (
              <ol className="m-0 grid list-none gap-3 p-0">
                {query.data.commonWrongAnswers.map((w) => (
                  <li key={w.activityId}>
                    <Card size="sm">
                      <CardContent className="grid gap-1">
                        <p className="m-0 font-medium">
                          {w.title}
                          {/* Not when the title already names it ("Objective 1 · item 1 of 5"). */}
                          {w.objectiveId !== null &&
                            !/^objective\b/i.test(w.title) &&
                            ` (objective ${w.objectiveId})`}
                        </p>
                        <p className="m-0">
                          {w.wrong} of {w.answered} got it wrong; {w.chosenBy} chose &ldquo;
                          {w.option}&rdquo;.
                        </p>
                        {w.whyWrong && (
                          <p className="m-0 text-sm text-muted-foreground">{w.whyWrong}</p>
                        )}
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </section>
  )
}
