import { useQuery } from '@tanstack/react-query'
import { Download } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { buttonVariants } from '@/components/ui/button-variants'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '../../components'
import { formatTime } from './formatTime.ts'
import { exportUrl, getInsights, type Insights } from './staff.api.ts'

/** A share of students as a thin bar, with the count beside it in text (so the bar is never the
 * only way to read the number). */
function Meter({ part, whole, label }: { part: number; whole: number; label: string }) {
  const share = whole === 0 ? 0 : part / whole
  return (
    <div className="flex min-w-36 items-center gap-2" title={`${label}: ${part} of ${whole}`}>
      <div className="h-2 flex-1 overflow-hidden rounded-sm bg-secondary" aria-hidden>
        <div className="h-full rounded-sm bg-primary" style={{ width: `${share * 100}%` }} />
      </div>
      <span className="w-14 text-right tabular-nums">
        {part} of {whole}
      </span>
    </div>
  )
}

function Totals({ data }: { data: Insights }) {
  const tiles = [
    ['Students', data.students],
    ['Answers', data.attempts],
    ['Hints viewed', data.hintsViewed],
  ] as const
  return (
    <div className="grid grid-cols-3 gap-3">
      {tiles.map(([label, value]) => (
        <Card key={label} size="sm">
          <CardContent className="grid gap-1">
            <span className="text-muted-foreground">{label}</span>
            <span className="text-2xl font-semibold tabular-nums">{value}</span>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function Activities({ data }: { data: Insights }) {
  return (
    <section className="grid gap-3" aria-labelledby="activities-heading">
      <div className="grid gap-1">
        <h2 id="activities-heading" className="text-xl font-semibold">
          Activities
        </h2>
        <p className="text-muted-foreground">
          Most wrong answers first. &quot;Needed hint 3 or 4&quot; counts as &quot;met with
          support&quot;: a high share means the activity or its explanation needs work.
        </p>
      </div>
      {data.activities.length === 0 ? (
        <p className="text-muted-foreground">No student has answered anything yet.</p>
      ) : (
        <Card size="sm">
          <CardContent className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-2 pr-4 font-medium">Activity</th>
                  <th className="py-2 pr-4 font-medium">Passed</th>
                  <th className="py-2 pr-4 text-right font-medium">Wrong answers</th>
                  <th className="py-2 font-medium">Needed hint 3 or 4</th>
                </tr>
              </thead>
              <tbody>
                {data.activities.map((a) => (
                  <tr key={a.id} className="border-t border-foreground/10">
                    <td className="py-2 pr-4">
                      <span className="font-medium">{a.title}</span>
                      <span className="block text-muted-foreground">
                        {a.kind.replaceAll('_', ' ')}
                      </span>
                    </td>
                    <td className="py-2 pr-4">
                      <Meter part={a.studentsPassed} whole={a.students} label="Students passed" />
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {a.wrongAttempts} of {a.attempts}
                    </td>
                    <td className="py-2">
                      <Meter
                        part={a.studentsWithSupport}
                        whole={a.students}
                        label="Students who needed hint 3 or 4"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </section>
  )
}

function Videos({ data }: { data: Insights }) {
  return (
    <section className="grid gap-3" aria-labelledby="videos-heading">
      <div className="grid gap-1">
        <h2 id="videos-heading" className="text-xl font-semibold">
          Videos
        </h2>
        <p className="text-muted-foreground">
          Out of everyone who started the video: who passed each checkpoint, and who watched to the
          end. A drop from one step to the next is where students stopped.
        </p>
      </div>
      {data.videos.length === 0 && (
        <p className="text-muted-foreground">No videos with checkpoints yet.</p>
      )}
      {data.videos.map((v) => (
        <Card key={v.id} size="sm">
          <CardHeader>
            <CardTitle className="font-semibold">{v.title}</CardTitle>
            <CardDescription>
              {v.students} student{v.students === 1 ? '' : 's'} started it
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="grid list-none gap-2 p-0">
              {v.checkpoints.map((c) => (
                <li key={c.id} className="grid items-center gap-2 sm:grid-cols-[1fr_16rem]">
                  <span>
                    <span className="text-muted-foreground tabular-nums">
                      {formatTime(c.atSeconds)}
                    </span>{' '}
                    {c.activityTitle}
                  </span>
                  <Meter part={c.studentsPassed} whole={v.students} label="Students passed" />
                </li>
              ))}
              <li className="grid items-center gap-2 sm:grid-cols-[1fr_16rem]">
                <span>Watched to the end</span>
                <Meter part={v.finished} whole={v.students} label="Students who finished" />
              </li>
            </ol>
          </CardContent>
        </Card>
      ))}
    </section>
  )
}

function Downloads() {
  const files = [
    {
      table: 'attempts',
      title: 'Attempts',
      file: 'attempts',
      text: 'Every answer: activity, right or wrong, score, highest hint seen, what was answered.',
    },
    {
      table: 'hints',
      title: 'Hints',
      file: 'hints',
      text: 'Every hint shown: activity, level and time.',
    },
    {
      table: 'events',
      title: 'Events',
      file: 'events',
      text: 'The timeline: segments viewed, videos started and finished, checkpoints reached, hints shown, results changing, modules completed.',
    },
    {
      table: 'objective_results',
      title: 'Objective results',
      file: 'objective-results',
      text: 'Each student’s result on each objective, and the answers it was decided from.',
    },
  ] as const
  return (
    <section className="grid gap-3" aria-labelledby="downloads-heading">
      <div className="grid gap-1">
        <h2 id="downloads-heading" className="text-xl font-semibold">
          Download for the evaluation
        </h2>
        <p className="text-muted-foreground">
          CSV files for the ID team&apos;s analysis. Students appear by internal number only, never
          by name or email. Staff and demo accounts are left out.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {files.map((f) => (
          <Card key={f.table} size="sm">
            <CardHeader>
              <CardTitle className="font-semibold">{f.title}</CardTitle>
              <CardDescription>{f.text}</CardDescription>
            </CardHeader>
            <CardContent>
              <a href={exportUrl(f.table)} download className={buttonVariants({ size: 'lg' })}>
                <Download aria-hidden />
                Download {f.file}.csv
              </a>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}

/** /staff/pilot — the pilot's numbers (ID document §8.4) and the evaluation CSVs (FR-10.2). */
export function StaffPilotPage() {
  const insights = useQuery({ queryKey: ['staff', 'insights'], queryFn: getInsights })
  return (
    <section className="grid gap-6" aria-labelledby="pilot-heading">
      <div className="grid gap-1">
        <h1 id="pilot-heading" className="text-3xl font-semibold">
          Pilot data
        </h1>
        <p className="text-muted-foreground">
          How students are getting on, from student accounts only. Updates every time the page
          loads.
        </p>
      </div>
      {insights.isPending && <Spinner label="Loading the pilot data" />}
      {insights.isError && (
        <Alert variant="destructive">
          <AlertDescription>{insights.error.message}</AlertDescription>
        </Alert>
      )}
      {insights.data && (
        <>
          <Totals data={insights.data} />
          <Activities data={insights.data} />
          <Videos data={insights.data} />
        </>
      )}
      <Downloads />
    </section>
  )
}
