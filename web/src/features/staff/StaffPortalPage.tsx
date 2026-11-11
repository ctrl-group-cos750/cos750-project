import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { STAFF_SECTIONS } from './sections.ts'
import { getInsights, listAccounts, listMembers, listVideos } from './staff.api.ts'

/** A short live count under a section's description, where the portal has one. */
function useSummaries(): Record<string, string | undefined> {
  const videos = useQuery({ queryKey: ['staff', 'videos'], queryFn: listVideos })
  const members = useQuery({ queryKey: ['staff', 'members'], queryFn: listMembers })
  const accounts = useQuery({ queryKey: ['staff', 'accounts'], queryFn: listAccounts })
  const insights = useQuery({ queryKey: ['staff', 'insights'], queryFn: getInsights })
  const count = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  return {
    videos: videos.data && count(videos.data.length, 'video'),
    members: members.data && count(members.data.length, 'team member'),
    accounts: accounts.data && count(accounts.data.length, 'account'),
    pilot: insights.data && `${count(insights.data.students, 'student')} so far`,
  }
}

/** /staff — the staff portal's front page: one card per setup area. */
export function StaffPortalPage() {
  const summaries = useSummaries()
  return (
    <section className="grid gap-6" aria-labelledby="staff-portal-heading">
      <div className="grid gap-1">
        <h1 id="staff-portal-heading" className="text-3xl font-semibold">
          Staff portal
        </h1>
        <p className="text-muted-foreground">Set up what students see in Ctrl Academy.</p>
      </div>
      <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        {STAFF_SECTIONS.map(({ path, title, description, icon: Icon }) => (
          <li key={path}>
            {/* The whole card is the link's click target (the link's ::after covers it). */}
            <Card className="relative h-full transition-shadow hover:ring-2 hover:ring-primary has-[a:focus-visible]:ring-3 has-[a:focus-visible]:ring-ring/50">
              <CardHeader>
                <Icon aria-hidden className="mb-2 size-6 text-primary" />
                <CardTitle className="text-lg font-semibold">
                  <Link
                    to={`/staff/${path}`}
                    className="text-card-foreground no-underline outline-none after:absolute after:inset-0"
                  >
                    {title}
                  </Link>
                </CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              {summaries[path] && (
                <CardContent className="font-medium text-primary">{summaries[path]}</CardContent>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
