import type { SavedVideo, StaffCheckpoint, StaffVideo } from './staff.api.ts'

/**
 * Moving a video between Ctrl Academy sites (staging → production). Staging and production have
 * separate databases and media volumes, so a video made on staging must be carried across: its
 * details as a JSON file, plus its MP4 and captions. Importing uploads the two files through the
 * normal upload (each stays under Cloudflare's 100 MB limit) and creates the video.
 */

export const FORMAT = 'ctrl-academy-video'
export const VERSION = 1

export type VideoExport = {
  format: typeof FORMAT
  version: typeof VERSION
  title: string
  transcript: string
  durationSeconds: number
  /** The file names the video and captions had on the site it came from, to help match them. */
  mediaFile: string
  captionsFile: string
  checkpoints: Omit<StaffCheckpoint, 'id'>[]
}

const fileName = (path: string) => path.split('/').pop() ?? path

/** The JSON for one saved video. Checkpoint ids are left out: they belong to the old site. */
export function toExport(video: SavedVideo): VideoExport {
  return {
    format: FORMAT,
    version: VERSION,
    title: video.title,
    transcript: video.transcript,
    durationSeconds: video.durationSeconds,
    mediaFile: fileName(video.mediaPath),
    captionsFile: fileName(video.captionsPath),
    checkpoints: video.checkpoints.map((c) => ({
      atSeconds: c.atSeconds,
      question: c.question,
      hints: c.hints,
    })),
  }
}

/** A file name for the download: "meet-bfs.video.json". */
export function exportFileName(title: string) {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${slug || 'video'}.video.json`
}

/** Reads an export file. Throws an Error with a message for staff when it isn't one. The API
 * checks everything again when the video is created. */
export function parseExport(text: string): VideoExport {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('This file is not JSON. Choose the .video.json file you exported.')
  }
  const d = data as Partial<VideoExport> | null
  if (!d || d.format !== FORMAT) {
    throw new Error('This is not a Ctrl Academy video export. Choose the .video.json file.')
  }
  if (d.version !== VERSION) {
    throw new Error(`This export is version ${String(d.version)}; this site reads version 1.`)
  }
  if (
    typeof d.title !== 'string' ||
    typeof d.transcript !== 'string' ||
    typeof d.durationSeconds !== 'number' ||
    !Array.isArray(d.checkpoints)
  ) {
    throw new Error('This export is incomplete. Export the video again.')
  }
  return d as VideoExport
}

/** The video to create from an export, once its two files are uploaded here. */
export function fromExport(
  exported: VideoExport,
  paths: { mediaPath: string; captionsPath: string },
): StaffVideo {
  return {
    title: exported.title,
    transcript: exported.transcript,
    durationSeconds: exported.durationSeconds,
    mediaPath: paths.mediaPath,
    captionsPath: paths.captionsPath,
    checkpoints: exported.checkpoints.map((c) => ({
      atSeconds: c.atSeconds,
      question: c.question,
      hints: c.hints,
    })),
  }
}
