import { useQuery } from '@tanstack/react-query'
import { Search, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { formatDate, listAccounts, matchesSearch } from './staff.api.ts'

/** /staff/accounts — every account that has been created, narrowed as you type. */
export function StaffAccountsPage() {
  const accounts = useQuery({ queryKey: ['staff', 'accounts'], queryFn: listAccounts })
  const [query, setQuery] = useState('')
  const shown = accounts.data?.filter((a) => matchesSearch(a, query)) ?? []

  return (
    <section className="grid gap-6" aria-labelledby="accounts-heading">
      <div className="grid gap-1">
        <h1 id="accounts-heading" className="text-3xl font-semibold">
          Accounts
        </h1>
        <p className="text-muted-foreground">
          Everyone who has registered. Open an account to see their progress.
        </p>
      </div>

      <div className="grid max-w-md gap-2">
        <Label htmlFor="account-search">Search by name or email</Label>
        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="account-search"
            type="search"
            autoComplete="off"
            className="pl-8"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      {accounts.isPending && <Spinner label="Loading accounts" />}
      {accounts.isError && (
        <Alert variant="destructive">
          <AlertDescription>{accounts.error.message}</AlertDescription>
        </Alert>
      )}
      {accounts.data && (
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {query.trim()
            ? `${shown.length} of ${accounts.data.length} accounts match`
            : `${accounts.data.length} account${accounts.data.length === 1 ? '' : 's'}`}
        </p>
      )}

      <ul className="grid list-none gap-3 p-0">
        {shown.map((a) => (
          <li key={a.id}>
            <Card
              size="sm"
              className="relative transition-shadow hover:ring-2 hover:ring-primary has-[a:focus-visible]:ring-3 has-[a:focus-visible]:ring-ring/50"
            >
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <div className="grid gap-0.5">
                  <span className="flex items-center gap-2 font-semibold">
                    <Link
                      to={`/staff/accounts/${a.id}`}
                      className="text-card-foreground no-underline outline-none after:absolute after:inset-0"
                    >
                      {a.displayName}
                    </Link>
                    {a.isStaff && (
                      <Badge variant="secondary">
                        <ShieldCheck aria-hidden />
                        Staff
                      </Badge>
                    )}
                  </span>
                  <span className="text-muted-foreground">{a.email}</span>
                </div>
                <div className="grid gap-0.5 text-right text-muted-foreground">
                  <span>Joined {formatDate(a.createdAt)}</span>
                  <span>
                    {a.lastActiveAt
                      ? `Last active ${formatDate(a.lastActiveAt, true)}`
                      : 'No activity yet'}
                  </span>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
      {accounts.data && query.trim() && shown.length === 0 && (
        <p className="text-muted-foreground">No account matches &quot;{query.trim()}&quot;.</p>
      )}
    </section>
  )
}
