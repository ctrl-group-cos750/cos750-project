import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, Spinner } from '../../components'
import { formatTime } from './formatTime.ts'
import { listVideos } from './staff.api.ts'

/** /staff/videos — every video, with a link to edit each and to make a new one. */
export function StaffVideosPage() {
  const videos = useQuery({ queryKey: ['staff', 'videos'], queryFn: listVideos })
  return (
    <section className="grid gap-6" aria-labelledby="staff-videos-heading">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 id="staff-videos-heading" className="text-3xl font-semibold">
          Videos
        </h1>
        <Link className={buttonVariants({ size: 'lg' })} to="/staff/videos/new">
          <Plus aria-hidden />
          New video
        </Link>
      </div>
      {videos.isPending && <Spinner label="Loading videos" />}
      {videos.isError && <Alert tone="danger">{videos.error.message}</Alert>}
      {videos.data?.length === 0 && (
        <p className="text-muted-foreground">
          No videos yet. Upload one with &quot;New video&quot;.
        </p>
      )}
      <ul className="grid list-none gap-3 p-0">
        {videos.data?.map((v) => (
          <li key={v.id}>
            <Card>
              <CardHeader>
                <CardTitle className="text-lg font-semibold">
                  <Link to={`/staff/videos/${v.id}`} className="text-primary">
                    {v.title}
                  </Link>
                </CardTitle>
                <CardDescription>
                  {formatTime(v.durationSeconds)} · {v.checkpointCount} checkpoint
                  {v.checkpointCount === 1 ? '' : 's'} ·{' '}
                  <Link to={`/videos/${v.id}`} className="text-primary">
                    student view
                  </Link>
                </CardDescription>
              </CardHeader>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
