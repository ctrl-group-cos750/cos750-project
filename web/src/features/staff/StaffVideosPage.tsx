import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { Alert, Card, Spinner } from '../../components'
import { formatTime } from './formatTime.ts'
import { listVideos } from './staff.api.ts'
import styles from './staff.module.css'

/** /staff/videos — every video, with a link to edit each and to make a new one. */
export function StaffVideosPage() {
  const videos = useQuery({ queryKey: ['staff', 'videos'], queryFn: listVideos })
  return (
    <>
      <div className={styles.titleRow}>
        <h1>Videos</h1>
        <Link className={styles.primaryLink} to="/staff/videos/new">
          New video
        </Link>
      </div>
      {videos.isPending && <Spinner label="Loading videos" />}
      {videos.isError && <Alert tone="danger">{videos.error.message}</Alert>}
      {videos.data?.length === 0 && <p>No videos yet. Upload one with &quot;New video&quot;.</p>}
      <ul className={styles.list}>
        {videos.data?.map((v) => (
          <li key={v.id}>
            <Card>
              <Link to={`/staff/videos/${v.id}`} className={styles.videoTitle}>
                {v.title}
              </Link>
              <p className={styles.muted}>
                {formatTime(v.durationSeconds)} · {v.checkpointCount} checkpoint
                {v.checkpointCount === 1 ? '' : 's'} ·{' '}
                <Link to={`/videos/${v.id}`}>student view</Link>
              </p>
            </Card>
          </li>
        ))}
      </ul>
    </>
  )
}
