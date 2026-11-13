import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, ShieldCheck, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCurrentUser } from '../../auth/hooks.ts'
import { Spinner } from '../../components'
import {
  addMember,
  deleteAccount,
  formatDate,
  getAccount,
  removeMember,
  type AccountDetail,
} from './staff.api.ts'

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card size="sm">
      <CardContent className="grid gap-1">
        <span className="text-muted-foreground">{label}</span>
        <span className="text-2xl font-semibold">{value}</span>
        {detail && <span className="text-muted-foreground">{detail}</span>}
      </CardContent>
    </Card>
  )
}

const percent = (part: number, whole: number) =>
  whole === 0 ? '' : `${Math.round((part / whole) * 100)}%`

function Stats({ account }: { account: AccountDetail }) {
  const s = account.stats
  return (
    <section className="grid gap-3" aria-labelledby="stats-heading">
      <h2 id="stats-heading" className="text-xl font-semibold">
        Stats
      </h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Answers submitted" value={String(s.attempts)} />
        <Stat
          label="Correct answers"
          value={String(s.correctAttempts)}
          detail={s.attempts ? `${percent(s.correctAttempts, s.attempts)} of answers` : undefined}
        />
        <Stat
          label="Activities passed"
          value={String(s.activitiesPassed)}
          detail={`of ${s.activitiesTried} tried`}
        />
        <Stat label="Hints viewed" value={String(s.hintsViewed)} />
      </div>
    </section>
  )
}

function Videos({ account }: { account: AccountDetail }) {
  return (
    <section className="grid gap-3" aria-labelledby="videos-heading">
      <h2 id="videos-heading" className="text-xl font-semibold">
        Videos
      </h2>
      {account.videos.length === 0 && (
        <p className="text-muted-foreground">No videos with checkpoints yet.</p>
      )}
      <ul className="grid list-none gap-3 p-0">
        {account.videos.map((v) => (
          <li key={v.id}>
            <Card size="sm">
              <CardContent className="grid gap-2">
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="font-semibold">{v.title}</span>
                  <span className="text-muted-foreground">
                    {v.checkpointsPassed} of {v.checkpointsTotal} checkpoints passed
                  </span>
                </div>
                <progress
                  className="h-2 w-full appearance-none overflow-hidden rounded-full bg-secondary [&::-moz-progress-bar]:bg-primary [&::-webkit-progress-bar]:bg-secondary [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-primary"
                  aria-label={`${v.title}: checkpoints passed`}
                  max={v.checkpointsTotal}
                  value={v.checkpointsPassed}
                />
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}

function RecentAnswers({ account }: { account: AccountDetail }) {
  return (
    <section className="grid gap-3" aria-labelledby="recent-heading">
      <h2 id="recent-heading" className="text-xl font-semibold">
        Recent answers
      </h2>
      {account.recentAttempts.length === 0 ? (
        <p className="text-muted-foreground">No answers yet.</p>
      ) : (
        <Card size="sm">
          <CardContent>
            <ul className="grid list-none gap-2 p-0">
              {account.recentAttempts.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    {a.correct ? (
                      <Badge variant="secondary">
                        <Check aria-hidden />
                        Correct
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <X aria-hidden />
                        Not yet
                      </Badge>
                    )}
                    {a.activityTitle}
                    {a.hintLevel > 0 && (
                      <span className="text-muted-foreground">(hint {a.hintLevel})</span>
                    )}
                  </span>
                  <span className="text-muted-foreground">{formatDate(a.createdAt, true)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </section>
  )
}

/** Make staff, or remove staff access: removing asks first, as on the members page. Not shown
 * on your own account. */
function Access({ account }: { account: AccountDetail }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const change = useMutation({
    mutationFn: () =>
      account.isStaff ? removeMember(account.id) : addMember(account.email).then(() => undefined),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['staff'] })
      setConfirming(false)
    },
  })
  // Focus follows the question: into it when it opens, back to the button when it closes.
  const trigger = useRef<HTMLButtonElement>(null)
  const confirm = useRef<HTMLButtonElement>(null)
  const wasConfirming = useRef(false)
  useEffect(() => {
    if (confirming) confirm.current?.focus()
    else if (wasConfirming.current) trigger.current?.focus()
    wasConfirming.current = confirming
  }, [confirming])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Staff access</CardTitle>
        <CardDescription>
          {account.isStaff
            ? `${account.displayName} can open the staff portal.`
            : `${account.displayName} is a student: no staff portal.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {!confirming && (
          <div>
            <Button
              ref={trigger}
              variant={account.isStaff ? 'outline' : 'default'}
              size="lg"
              disabled={change.isPending}
              focusableWhenDisabled
              onClick={() => (account.isStaff ? setConfirming(true) : change.mutate())}
            >
              <ShieldCheck aria-hidden />
              {account.isStaff ? 'Remove staff access' : 'Make staff'}
            </Button>
          </div>
        )}
        {confirming && (
          <Alert
            onKeyDown={(event) => {
              if (event.key === 'Escape') setConfirming(false)
            }}
          >
            <AlertTitle>Remove {account.displayName}&apos;s staff access?</AlertTitle>
            <AlertDescription className="grid gap-3">
              <p>
                They keep their account, but lose the staff portal straight away. You can add them
                again later.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  ref={confirm}
                  variant="destructive"
                  disabled={change.isPending}
                  focusableWhenDisabled
                  onClick={() => change.mutate()}
                >
                  {change.isPending ? 'Removing...' : 'Remove access'}
                </Button>
                <Button variant="outline" onClick={() => setConfirming(false)}>
                  Cancel
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}
        {change.isError && (
          <Alert variant="destructive">
            <AlertDescription>{change.error.message}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

/** Delete the account. Can't be undone, so the email has to be typed out first. */
function DeleteAccount({ account }: { account: AccountDetail }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [typed, setTyped] = useState('')
  const remove = useMutation({
    mutationFn: () => deleteAccount(account.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['staff', 'accounts', account.id] })
      void queryClient.invalidateQueries({ queryKey: ['staff'] })
      // The list says it was deleted and takes focus (A13).
      void navigate('/staff/accounts', {
        replace: true,
        state: { deleted: account.displayName },
      })
    },
  })
  const confirmed = typed.trim().toLowerCase() === account.email

  return (
    <Card className="ring-destructive/40">
      <CardHeader>
        <CardTitle className="text-lg font-semibold text-destructive">Delete account</CardTitle>
        <CardDescription>
          Deletes {account.displayName}&apos;s account and everything stored about it: every answer
          and every hint. They are logged out straight away. This can&apos;t be undone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (confirmed) remove.mutate()
          }}
        >
          <div className="grid max-w-md gap-2">
            <Label htmlFor="confirm-email">Type {account.email} to confirm</Label>
            <Input
              id="confirm-email"
              autoComplete="off"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
            />
          </div>
          <div>
            <Button
              type="submit"
              variant="destructive"
              size="lg"
              disabled={!confirmed || remove.isPending}
            >
              <Trash2 aria-hidden />
              {remove.isPending ? 'Deleting...' : 'Delete account'}
            </Button>
          </div>
          {remove.isError && (
            <Alert variant="destructive">
              <AlertTitle>Not deleted</AlertTitle>
              <AlertDescription>{remove.error.message}</AlertDescription>
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

/** /staff/accounts/:accountId — one account's overview: stats, video progress, recent answers,
 * staff access and deleting the account. */
export function StaffAccountPage() {
  const id = Number(useParams().accountId)
  const { data: me } = useCurrentUser()
  const account = useQuery({ queryKey: ['staff', 'accounts', id], queryFn: () => getAccount(id) })
  const isYou = me?.id === id

  return (
    <section className="grid gap-6" aria-labelledby="account-heading">
      <Link to="/staff/accounts" className="flex w-fit items-center gap-1 text-primary">
        <ArrowLeft aria-hidden className="size-4" />
        All accounts
      </Link>
      {account.isPending && <Spinner label="Loading the account" />}
      {account.isError && (
        <Alert variant="destructive">
          <AlertDescription>{account.error.message}</AlertDescription>
        </Alert>
      )}
      {account.data && (
        <>
          <div className="grid gap-1">
            <h1
              id="account-heading"
              className="flex flex-wrap items-center gap-3 text-3xl font-semibold"
            >
              {account.data.displayName}
              {account.data.isStaff && (
                <Badge variant="secondary">
                  <ShieldCheck aria-hidden />
                  Staff
                </Badge>
              )}
              {isYou && <Badge variant="outline">You</Badge>}
            </h1>
            <p className="text-muted-foreground">
              {account.data.email} · joined {formatDate(account.data.createdAt)} ·{' '}
              {account.data.lastActiveAt
                ? `last active ${formatDate(account.data.lastActiveAt, true)}`
                : 'no activity yet'}
            </p>
          </div>
          <Stats account={account.data} />
          <Videos account={account.data} />
          <RecentAnswers account={account.data} />
          {!isYou && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Access account={account.data} />
              <DeleteAccount account={account.data} />
            </div>
          )}
        </>
      )}
    </section>
  )
}
