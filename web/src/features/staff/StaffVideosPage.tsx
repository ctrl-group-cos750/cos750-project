import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, FileDown, Plus, Upload } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, Spinner } from '../../components'
import { formatTime } from './formatTime.ts'
import { getVideo, listVideos } from './staff.api.ts'
import { exportFileName, toExport } from './videoTransfer.ts'

/** Saves `text` as a file. The CSP blocks blob: only for media, not for a download link. */
function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

/** "Export": the three files another site's "Import a video" needs. */
function ExportLinks({ id }: { id: number }) {
  const load = useMutation({ mutationFn: () => getVideo(id) })
  if (!load.data) {
    return (
      <div className="grid gap-2">
        <div>
          <Button variant="outline" disabled={load.isPending} onClick={() => load.mutate()}>
            <FileDown aria-hidden />
            {load.isPending ? 'Preparing...' : 'Export'}
          </Button>
        </div>
        {load.isError && <p className="text-destructive">{load.error.message}</p>}
      </div>
    )
  }
  const video = load.data
  const link = buttonVariants({ variant: 'outline' })
  return (
    <div className="grid gap-2">
      <p className="text-muted-foreground">
        Download all three, then use &quot;Import video&quot; on the other site.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          onClick={() =>
            download(exportFileName(video.title), JSON.stringify(toExport(video), null, 2))
          }
        >
          <Download aria-hidden />
          Details (.json)
        </Button>
        <a className={link} href={video.mediaPath} download>
          <Download aria-hidden />
          Video (.mp4)
        </a>
        <a className={link} href={video.captionsPath} download>
          <Download aria-hidden />
          Captions (.vtt)
        </a>
      </div>
    </div>
  )
}

/** /staff/videos — every video, with a link to edit each and to make a new one. */
export function StaffVideosPage() {
  const videos = useQuery({ queryKey: ['staff', 'videos'], queryFn: listVideos })
  return (
    <section className="grid gap-6" aria-labelledby="staff-videos-heading">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 id="staff-videos-heading" className="text-3xl font-semibold">
          Videos
        </h1>
        <div className="flex flex-wrap gap-2">
          <Link
            className={buttonVariants({ variant: 'outline', size: 'lg' })}
            to="/staff/videos/import"
          >
            <Upload aria-hidden />
            Import video
          </Link>
          <Link className={buttonVariants({ size: 'lg' })} to="/staff/videos/new">
            <Plus aria-hidden />
            New video
          </Link>
        </div>
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
              <CardContent>
                <ExportLinks id={v.id} />
              </CardContent>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
