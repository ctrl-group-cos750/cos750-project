import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCurrentUser } from '../../auth/hooks.ts'
import { Spinner } from '../../components'
import { addMember, listMembers, removeMember, type StaffMember } from './staff.api.ts'

const MEMBERS = ['staff', 'members']

/** Make an existing account staff by its email. */
function AddMemberForm() {
  const queryClient = useQueryClient()
  const [email, setEmail] = useState('')
  const add = useMutation({
    mutationFn: addMember,
    onSuccess: () => {
      setEmail('')
      void queryClient.invalidateQueries({ queryKey: MEMBERS })
    },
  })

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (email.trim()) add.mutate(email.trim())
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Add a team member</CardTitle>
        <CardDescription>
          They need an account first: ask them to register in the app, then enter the email they
          used.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="member-email">Email</Label>
            <div className="flex flex-wrap gap-3">
              <Input
                id="member-email"
                type="email"
                autoComplete="off"
                required
                className="max-w-sm flex-1"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-invalid={add.isError || undefined}
              />
              <Button type="submit" size="lg" disabled={add.isPending}>
                <UserPlus aria-hidden />
                {add.isPending ? 'Adding...' : 'Make staff'}
              </Button>
            </div>
          </div>
          {add.isError && (
            <Alert variant="destructive">
              <AlertTitle>Not added</AlertTitle>
              <AlertDescription>{add.error.message}</AlertDescription>
            </Alert>
          )}
          {add.isSuccess && (
            <Alert className="border-success bg-success/15">
              <AlertTitle>{add.data.displayName} is a team member</AlertTitle>
              <AlertDescription>
                They see the staff portal the next time a page loads.
              </AlertDescription>
            </Alert>
          )}
        </form>
      </CardContent>
    </Card>
  )
}

/** One team member, with "Remove access" behind a confirmation. Never on your own row. */
function MemberRow({ member, isYou }: { member: StaffMember; isYou: boolean }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const remove = useMutation({
    mutationFn: removeMember,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: MEMBERS }),
  })

  return (
    <Card size="sm">
      <CardContent className="grid gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="grid gap-0.5">
            <span className="font-semibold">
              {member.displayName}
              {isYou && <span className="font-normal text-muted-foreground"> (you)</span>}
            </span>
            <span className="text-muted-foreground">{member.email}</span>
          </div>
          {!isYou && !confirming && (
            <Button variant="destructive" onClick={() => setConfirming(true)}>
              Remove access
            </Button>
          )}
        </div>
        {confirming && (
          <Alert>
            <AlertTitle>Remove {member.displayName}&apos;s staff access?</AlertTitle>
            <AlertDescription className="grid gap-3">
              <p>
                They keep their account, but lose the staff portal straight away. You can add them
                again later.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="destructive"
                  disabled={remove.isPending}
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
        <h2 id="current-members-heading" className="text-xl font-semibold">
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
              <MemberRow member={m} isYou={m.id === me?.id} />
            </li>
          ))}
        </ul>
      </section>
    </section>
  )
}
