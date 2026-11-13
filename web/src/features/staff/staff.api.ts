import { api, ApiError, OFFLINE_MESSAGE } from '../../api/client.ts'

/** The staff video editor's API (api/app/routers/staff.py). Unlike the student API, questions
 * here carry the correct option and the feedback. */

export type StaffQuestion = {
  prompt: string
  options: { id: string; label: string }[]
  correct: string
  feedback: Record<string, string>
}

export type StaffHint = { level: number; body: string }

export type StaffCheckpoint = {
  /** Left out for a new checkpoint; kept for an existing one so its attempts stay linked. */
  id?: number
  atSeconds: number
  question: StaffQuestion
  hints: StaffHint[]
}

export type StaffVideo = {
  title: string
  mediaPath: string
  captionsPath: string
  transcript: string
  durationSeconds: number
  checkpoints: StaffCheckpoint[]
}

export type SavedVideo = StaffVideo & {
  id: number
  checkpoints: (StaffCheckpoint & { id: number; activityId: number })[]
}

export type VideoSummary = {
  id: number
  title: string
  durationSeconds: number
  checkpointCount: number
}

export const listVideos = () => api<VideoSummary[]>('/api/staff/videos')
export const getVideo = (id: number) => api<SavedVideo>(`/api/staff/videos/${id}`)
export const createVideo = (video: StaffVideo) =>
  api<SavedVideo>('/api/staff/videos', { method: 'POST', body: video })
export const updateVideo = (id: number, video: StaffVideo) =>
  api<SavedVideo>(`/api/staff/videos/${id}`, { method: 'PUT', body: video })

export type MediaKind = 'video' | 'captions'
const CONTENT_TYPES: Record<MediaKind, string> = { video: 'video/mp4', captions: 'text/vtt' }

/**
 * Uploads one file to the media volume and resolves to its /media/… path. Uses XMLHttpRequest,
 * not fetch, because fetch can't report upload progress and a video can take a while.
 */
export function uploadMedia(
  kind: MediaKind,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/staff/media?kind=${kind}`)
    xhr.setRequestHeader('Content-Type', CONTENT_TYPES[kind])
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
    xhr.onerror = () => reject(new ApiError(0, OFFLINE_MESSAGE))
    xhr.onload = () => {
      let body: { path?: string; detail?: unknown } = {}
      try {
        body = JSON.parse(xhr.responseText) as typeof body
      } catch {
        // not JSON: fall through to the generic message
      }
      if (xhr.status === 201 && body.path) resolve(body.path)
      else
        reject(
          new ApiError(
            xhr.status,
            typeof body.detail === 'string' ? body.detail : 'The upload failed. Try again.',
          ),
        )
    }
    xhr.send(file)
  })
}

/** A team member on the "Staff members" page. */
export type StaffMember = { id: number; email: string; displayName: string }

export const listMembers = () => api<StaffMember[]>('/api/staff/members')
/** Makes the existing account with this email staff. 404 when no account uses it. */
export const addMember = (email: string) =>
  api<StaffMember>('/api/staff/members', { method: 'POST', body: { email } })
/** Takes staff access away. The API refuses (409) when it is your own. */
export const removeMember = (id: number) =>
  api<undefined>(`/api/staff/members/${id}`, { method: 'DELETE' })

/** One row of the staff portal's accounts list (api/app/schemas/accounts.py). */
export type AccountSummary = {
  id: number
  email: string
  displayName: string
  isStaff: boolean
  createdAt: string
  /** The latest answer or hint; null if they have done nothing yet. */
  lastActiveAt: string | null
}

export type AccountDetail = AccountSummary & {
  stats: {
    attempts: number
    correctAttempts: number
    activitiesTried: number
    activitiesPassed: number
    hintsViewed: number
  }
  videos: { id: number; title: string; checkpointsPassed: number; checkpointsTotal: number }[]
  recentAttempts: {
    id: number
    activityTitle: string
    kind: string
    correct: boolean
    hintLevel: number
    createdAt: string
  }[]
}

export const listAccounts = () => api<AccountSummary[]>('/api/staff/accounts')
export const getAccount = (id: number) => api<AccountDetail>(`/api/staff/accounts/${id}`)
/** Deletes the account and everything stored about it. The API refuses (409) your own. */
export const deleteAccount = (id: number) =>
  api<undefined>(`/api/staff/accounts/${id}`, { method: 'DELETE' })

/** Whether an account matches what was typed in a search box: part of the name or email. */
export function matchesSearch(account: { email: string; displayName: string }, query: string) {
  const q = query.trim().toLowerCase()
  return (
    !q || account.email.toLowerCase().includes(q) || account.displayName.toLowerCase().includes(q)
  )
}

/** "5 Nov 2026", or "5 Nov 2026, 14:30" with the time. */
export function formatDate(iso: string, withTime = false) {
  return new Intl.DateTimeFormat('en-ZA', {
    dateStyle: 'medium',
    ...(withTime ? { timeStyle: 'short' } : {}),
  }).format(new Date(iso))
}

/** The "Pilot data" page (api/app/schemas/evaluation.py): counts over student accounts only. */
export type Insights = {
  students: number
  attempts: number
  hintsViewed: number
  activities: {
    id: number
    title: string
    kind: string
    students: number
    attempts: number
    wrongAttempts: number
    studentsPassed: number
    studentsWithSupport: number
  }[]
  videos: {
    id: number
    title: string
    /** Started it, or answered one of its checkpoints. */
    students: number
    /** Watched it to the end. */
    finished: number
    checkpoints: { id: number; atSeconds: number; activityTitle: string; studentsPassed: number }[]
  }[]
}

export const getInsights = () => api<Insights>('/api/staff/insights')

/** "Before the lecture" (api/app/schemas/evaluation.py Readiness): counts over student accounts. */
export type Readiness = {
  /** Students who have answered at least one mastery item. */
  students: number
  /** Of them, how many met every objective. */
  ready: number
  objectives: {
    id: number
    text: string
    metIndependently: number
    metWithSupport: number
    notYet: number
  }[]
  commonWrongAnswers: {
    activityId: number
    title: string
    objectiveId: number | null
    answered: number
    wrong: number
    option: string
    chosenBy: number
    whyWrong: string | null
  }[]
}

export const getReadiness = () => api<Readiness>('/api/staff/readiness')
/** CSV downloads: a plain link, so the browser saves the file with the session cookie. */
export type ExportTable = 'attempts' | 'hints' | 'events' | 'objective_results'
export const exportUrl = (table: ExportTable) => `/api/staff/export/${table}.csv`
