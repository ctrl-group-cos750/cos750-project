import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, UserPlus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCurrentUser } from '../../auth/hooks.ts'
import { Spinner } from '../../components'
import {
  addMember,
  getAccount,
  listAccounts,
  listMembers,
  matchesSearch,
  removeMember,
  type StaffMember,
} from './staff.api.ts'

const MEMBERS = ['staff', 'members']
const MAX_MATCHES = 8

/** Find a registered account by name or email (the list narrows as you type) and make it staff. */
function AddMemberForm() {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const accounts = useQuery({ queryKey: ['staff', 'accounts'], queryFn: listAccounts })
  // The list masks students' emails (NFR-S8, #146), so the full one comes from their account.
  const add = useMutation({
    mutationFn: (id: number) => getAccount(id).then((account) => addMember(account.email)),
    onSuccess: () => {
      setQuery('')
      void queryClient.invalidateQueries({ queryKey: ['staff'] })
    },
  })
  // The results (and the button pressed) go once someone is added: focus the message instead.
  const added = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (add.data) added.current?.focus()
  }, [add.data])
  const students = accounts.data?.filter((a) => !a.isStaff) ?? []
  const matches = query.trim() ? students.filter((a) => matchesSearch(a, query)) : []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Add a team member</CardTitle>
        <CardDescription>
          Start typing their name or email. They need an account first: ask them to register in the
          app.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid max-w-md gap-2">
          <Label htmlFor="member-search">Name or email</Label>
          <div className="relative">
            <Search
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="member-search"
              type="search"
              autoComplete="off"
              className="pl-8"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
        {accounts.isError && (
          <Alert variant="destructive">
            <AlertDescription>{accounts.error.message}</AlertDescription>
          </Alert>
        )}
        {query.trim() && accounts.data && (
          <div aria-live="polite" className="grid gap-2">
            {matches.length === 0 ? (
              <p className="text-muted-foreground">
                No student account matches &quot;{query.trim()}&quot;. They need to register in the
                app first.
              </p>
            ) : (
              <ul aria-label="Matching accounts" className="grid list-none gap-2 p-0">
                {matches.slice(0, MAX_MATCHES).map((a) => (
                  <li
                    key={a.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-background/60 px-3 py-2"
                  >
                    <div className="grid gap-0.5">
                      <span className="font-semibold">{a.displayName}</span>
                      <span className="text-muted-foreground">{a.email}</span>
                    </div>
                    <Button
                      disabled={add.isPending}
                      focusableWhenDisabled
                      onClick={() => add.mutate(a.id)}
                      aria-label={`Make ${a.displayName} staff`}
                    >
                      <UserPlus aria-hidden />
                      Make staff
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {matches.length > MAX_MATCHES && (
              <p className="text-sm text-muted-foreground">
                {matches.length - MAX_MATCHES} more: keep typing to narrow it down.
              </p>
            )}
          </div>
        )}
        {add.isError && (
          <Alert variant="destructive">
            <AlertTitle>Not added</AlertTitle>
            <AlertDescription>{add.error.message}</AlertDescription>
          </Alert>
        )}
        {add.isSuccess && (
          <Alert ref={added} tabIndex={-1} className="border-success bg-success/15">
            <AlertTitle>{add.data.displayName} is a team member</AlertTitle>
            {/* Full-strength text: the muted colour fails 4.5:1 on the success tint. */}
            <AlertDescription className="text-foreground">
              They see the staff portal the next time a page loads.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

/** One team member, with "Remove access" behind a confirmation. Never on your own row. */
function MemberRow({
  member,
  isYou,
  onRemoved,
}: {
  member: StaffMember
  isYou: boolean
  /** After access is removed and the row is about to go: where focus should go. */
  onRemoved: () => void
}) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const remove = useMutation({
    mutationFn: removeMember,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['staff'] })
      onRemoved()
    },
  })
  // Focus follows the question (WCAG 2.4.3): to its "Remove access" when it opens, and back to
  // the row's own button when it is cancelled, never to the page.
  const trigger = useRef<HTMLButtonElement>(null)
  const confirm = useRef<HTMLButtonElement>(null)
  const wasConfirming = useRef(false)
  useEffect(() => {
    if (confirming) confirm.current?.focus()
    else if (wasConfirming.current) trigger.current?.focus()
    wasConfirming.current = confirming
  }, [confirming])

  return (
    <Card size="sm">
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="grid gap-0.5">
            <span className="font-semibold">
              <Link to={`/staff/accounts/${member.id}`} className="text-card-foreground">
                {member.displayName}
              </Link>
              {isYou && <span className="font-normal text-muted-foreground"> (you)</span>}
            </span>
            <span className="text-muted-foreground">{member.email}</span>
          </div>
          {!isYou && !confirming && (
            <Button ref={trigger} variant="destructive" onClick={() => setConfirming(true)}>
              Remove access
            </Button>
          )}
        </div>
        {confirming && (
          <Alert
            onKeyDown={(event) => {
              if (event.key === 'Escape') setConfirming(false)
            }}
          >
            <AlertTitle>Remove {member.displayName}&apos;s staff access?</AlertTitle>
            <AlertDescription className="grid gap-3">
              <p>
                They keep their account, but lose the staff portal straight away. You can add them
                again later.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  ref={confirm}
                  variant="destructive"
                  disabled={remove.isPending}
                  focusableWhenDisabled
                  onClick={() => remove.mutate(member.id)}
                >
                  {remove.isPending ? 'Removing...' : 'Remove access'}
                </Button>
                <Button variant="outline" onClick={() => setConfirming(false)}>
                  Cancel
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}
        {remove.isError && (
          <Alert variant="destructive">
            <AlertTitle>Not removed</AlertTitle>
            <AlertDescription>{remove.error.message}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}

/** /staff/members — who can open the staff portal, and adding or removing them. */
export function StaffMembersPage() {
  const { data: me } = useCurrentUser()
  const members = useQuery({ queryKey: MEMBERS, queryFn: listMembers })
  const membersHeading = useRef<HTMLHeadingElement>(null)
  return (
    <section className="grid gap-6" aria-labelledby="staff-members-heading">
      <div className="grid gap-1">
        <h1 id="staff-members-heading" className="text-3xl font-semibold">
          Staff members
        </h1>
        <p className="text-muted-foreground">
          Team members can open the staff portal and change what students see.
        </p>
      </div>
      <AddMemberForm />
      <section className="grid gap-3" aria-labelledby="current-members-heading">
        <h2
          ref={membersHeading}
          id="current-members-heading"
          tabIndex={-1}
          className="text-xl font-semibold"
        >
          Current team members
        </h2>
        {members.isPending && <Spinner label="Loading team members" />}
        {members.isError && (
          <Alert variant="destructive">
            <AlertDescription>{members.error.message}</AlertDescription>
          </Alert>
        )}
        <ul className="grid list-none gap-3 p-0">
          {members.data?.map((m) => (
            <li key={m.id}>
              <MemberRow
                member={m}
                isYou={m.id === me?.id}
                onRemoved={() => membersHeading.current?.focus()}
              />
            </li>
          ))}
        </ul>
      </section>
    </section>
  )
}
