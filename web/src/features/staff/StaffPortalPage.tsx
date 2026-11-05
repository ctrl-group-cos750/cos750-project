import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Card } from '../../components'
import { STAFF_SECTIONS } from './sections.ts'
import { listVideos } from './staff.api.ts'
import styles from './StaffPortalPage.module.css'

/** A short live count under a section's description, where the portal has one. */
function useSummaries(): Record<string, string | undefined> {
  const videos = useQuery({ queryKey: ['staff', 'videos'], queryFn: listVideos })
  return {
    videos: videos.data && `${videos.data.length} video${videos.data.length === 1 ? '' : 's'}`,
  }
}

/** /staff — the staff portal's front page: one card per setup area. */
export function StaffPortalPage() {
  const summaries = useSummaries()
  return (
    <>
      <h1>Staff portal</h1>
      <p className={styles.intro}>Set up what students see in Ctrl Academy.</p>
      <ul className={styles.grid}>
        {STAFF_SECTIONS.map((s) => (
          <li key={s.path}>
            <Card interactive className={styles.card}>
              <h2 className={styles.title}>
                <Link to={`/staff/${s.path}`} className={styles.link}>
                  {s.title}
                </Link>
              </h2>
              <p className={styles.description}>{s.description}</p>
              {summaries[s.path] && <p className={styles.summary}>{summaries[s.path]}</p>}
            </Card>
          </li>
        ))}
      </ul>
    </>
  )
}
