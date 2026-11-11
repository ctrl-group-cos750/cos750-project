import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Upload } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createVideo, uploadMedia } from './staff.api.ts'
import { fromExport, parseExport, type VideoExport } from './videoTransfer.ts'

type Step = { label: string; progress: number }

/** /staff/videos/import — make a video from another site's export (staging → production): the
 * .video.json file plus its MP4 and captions. */
export function StaffVideoImportPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [details, setDetails] = useState<VideoExport>()
  const [detailsError, setDetailsError] = useState('')
  const [video, setVideo] = useState<File>()
  const [captions, setCaptions] = useState<File>()
  const [step, setStep] = useState<Step>()

  async function chooseDetails(file: File | undefined) {
    setDetails(undefined)
    setDetailsError('')
    if (!file) return
    try {
      setDetails(parseExport(await file.text()))
    } catch (error) {
      setDetailsError((error as Error).message)
    }
  }

  const run = useMutation({
    mutationFn: async () => {
      if (!details || !video || !captions) throw new Error('Choose all three files first.')
      setStep({ label: 'Uploading the video', progress: 0 })
      const mediaPath = await uploadMedia('video', video, (p) =>
        setStep({ label: 'Uploading the video', progress: p }),
      )
      setStep({ label: 'Uploading the captions', progress: 0 })
      const captionsPath = await uploadMedia('captions', captions, (p) =>
        setStep({ label: 'Uploading the captions', progress: p }),
      )
      setStep({ label: 'Creating the video', progress: 1 })
      return createVideo(fromExport(details, { mediaPath, captionsPath }))
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['staff'] })
      void navigate(`/staff/videos/${saved.id}`, { replace: true })
    },
    onSettled: () => setStep(undefined),
  })

  const mismatch = [
    details && video && video.name !== details.mediaFile && `the video is ${details.mediaFile}`,
    details &&
      captions &&
      captions.name !== details.captionsFile &&
      `the captions are ${details.captionsFile}`,
  ].filter(Boolean)

  return (
    <section className="grid gap-6" aria-labelledby="import-heading">
      <Link to="/staff/videos" className="flex w-fit items-center gap-1 text-primary">
        <ArrowLeft aria-hidden className="size-4" />
        All videos
      </Link>
      <div className="grid gap-1">
        <h1 id="import-heading" className="text-3xl font-semibold">
          Import a video
        </h1>
        <p className="text-muted-foreground">
          Brings a video from another Ctrl Academy site, such as staging, with its checkpoints,
          questions and hints. On the other site, open Videos and use the three export links on the
          video, then choose those files here.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Files</CardTitle>
          <CardDescription>The video can be up to 95 MB, the captions up to 1 MB.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              run.mutate()
            }}
          >
            <div className="grid max-w-md gap-2">
              <Label htmlFor="import-details">Details (.video.json)</Label>
              <Input
                id="import-details"
                type="file"
                accept=".json,application/json"
                onChange={(e) => void chooseDetails(e.target.files?.[0])}
                aria-invalid={detailsError ? true : undefined}
              />
              {detailsError && <p className="text-destructive">{detailsError}</p>}
              {details && (
                <p className="text-muted-foreground">
                  &quot;{details.title}&quot;, {details.checkpoints.length} checkpoint
                  {details.checkpoints.length === 1 ? '' : 's'}
                </p>
              )}
            </div>
            <div className="grid max-w-md gap-2">
              <Label htmlFor="import-video">Video (.mp4)</Label>
              <Input
                id="import-video"
                type="file"
                accept="video/mp4"
                onChange={(e) => setVideo(e.target.files?.[0])}
              />
            </div>
            <div className="grid max-w-md gap-2">
              <Label htmlFor="import-captions">Captions (.vtt)</Label>
              <Input
                id="import-captions"
                type="file"
                accept=".vtt,text/vtt"
                onChange={(e) => setCaptions(e.target.files?.[0])}
              />
            </div>

            {mismatch.length > 0 && (
              <Alert>
                <AlertTitle>Check these are the right files</AlertTitle>
                <AlertDescription>
                  The export says {mismatch.join(' and ')}. That&apos;s fine if you renamed them.
                </AlertDescription>
              </Alert>
            )}

            {step && (
              <div className="grid max-w-md gap-1">
                <span>{step.label}</span>
                <progress
                  className="h-2 w-full appearance-none overflow-hidden rounded-full bg-secondary [&::-moz-progress-bar]:bg-primary [&::-webkit-progress-bar]:bg-secondary [&::-webkit-progress-value]:bg-primary"
                  aria-label={step.label}
                  max={1}
                  value={step.progress}
                />
              </div>
            )}
            {run.isError && (
              <Alert variant="destructive">
                <AlertTitle>Not imported</AlertTitle>
                <AlertDescription>{run.error.message}</AlertDescription>
              </Alert>
            )}

            <div>
              <Button
                type="submit"
                size="lg"
                disabled={!details || !video || !captions || run.isPending}
              >
                <Upload aria-hidden />
                {run.isPending ? 'Importing...' : 'Import video'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </section>
  )
}
