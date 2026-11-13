import {
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
} from 'react'
import { Link, useLocation } from 'react-router'
import { ApiError } from '../../api/client.ts'
import type { User } from '../../auth/api.ts'
import { useCurrentUser } from '../../auth/hooks.ts'
import { PasswordChecklist } from '../../auth/PasswordChecklist.tsx'
import { focusFirstError, newPasswordError, type FieldErrors } from '../../auth/validation.ts'
import {
  AVATARS,
  Alert,
  Avatar,
  Button,
  Card,
  Spinner,
  TextField,
  avatarName,
  type AvatarId,
} from '../../components'
import { useReport } from '../mastery/hooks.ts'
import { prefersReducedMotion, useConfettiSetting } from '../progress/confetti.ts'
import { usePreference } from '../progress/preferences.ts'
import { useRewards, useRewardsSettings } from '../rewards/hooks.ts'
import { useChangePassword, useDeletePicture, useSetAvatar, useUploadPicture } from './hooks.ts'
import { squarePicture } from './squarePicture.ts'
import styles from './ProfilePage.module.css'

/** Points, badges and objectives met (FR-1.7): the student's own, never anyone else's. Points and
 * badges respect "hide" (FR-9.5); the mastery results are always shown. */
function Stats() {
  const rewards = useRewards()
  const report = useReport()
  const hidden = rewards.data?.hideRewards ?? false
  const met = report.data?.objectives.filter((o) => o.state.startsWith('met_')).length ?? 0
  const total = report.data?.objectives.length ?? 0

  const tiles: [string, string][] = [
    ['Objectives met', report.isPending ? '…' : `${met} of ${total}`],
    ...(hidden
      ? []
      : ([
          ['Points', rewards.isPending ? '…' : String(rewards.data?.points ?? 0)],
          ['Badges', rewards.isPending ? '…' : String(rewards.data?.badges.length ?? 0)],
        ] as [string, string][])),
  ]
  return (
    <section aria-labelledby="stats-heading" className={styles.section}>
      <h2 id="stats-heading">Your progress</h2>
      <dl className={styles.tiles}>
        {tiles.map(([label, value]) => (
          <Card key={label} className={styles.tile}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </Card>
        ))}
      </dl>
      {report.data?.ready && <p>You're ready for the lecture.</p>}
      <p className={styles.links}>
        <Link to="/report">See your mastery report</Link>
        {!hidden && <Link to="/badges">See your badges</Link>}
      </p>
    </section>
  )
}

/** Upload a picture of their own, or choose one from the team's set (FR-1.6). Saved at once.
 * Nothing here is disabled while it saves, so keyboard focus never drops to the page (WCAG
 * 2.4.3): arrowing through the pictures saves the last one chosen, and a press that can't run yet
 * is ignored (aria-disabled). */
function Picture({ user }: { user: User }) {
  const setAvatar = useSetAvatar()
  const upload = useUploadPicture()
  const remove = useDeletePicture()
  const [problem, setProblem] = useState<string | null>(null)
  const [preparing, setPreparing] = useState(false)
  // A picture chosen while another was saving: saved as soon as that one is done.
  const [queued, setQueued] = useState<{ choice: AvatarId | null } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const name = useId()
  const uploadId = useId()
  const choices: (AvatarId | null)[] = [null, ...AVATARS]
  const fileBusy = upload.isPending || remove.isPending || preparing
  const busy = setAvatar.isPending || fileBusy
  // Show the picked picture straight away, while it saves; the saved one again if saving fails.
  const shown = queued
    ? queued.choice
    : setAvatar.isPending
      ? setAvatar.variables
      : user.pictureUrl
        ? 'own'
        : user.avatar
  const error = problem ?? (setAvatar.error ?? upload.error ?? remove.error)?.message
  const saved = setAvatar.isSuccess || upload.isSuccess || remove.isSuccess

  const queue = useRef<{ choice: AvatarId | null } | null>(null)

  function save(choice: AvatarId | null) {
    setAvatar.mutate(choice, {
      onSettled: () => {
        const next = queue.current
        queue.current = null
        setQueued(null)
        if (next) save(next.choice)
      },
    })
  }
  function pick(choice: AvatarId | null) {
    if (fileBusy) return
    if (setAvatar.isPending) {
      queue.current = { choice }
      setQueued({ choice })
    } else save(choice)
  }

  async function choose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // choosing the same file again still uploads it
    if (!file) return
    setProblem(null)
    setPreparing(true)
    try {
      upload.mutate(await squarePicture(file))
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'This picture could not be used.')
    } finally {
      setPreparing(false)
    }
  }

  return (
    <section aria-labelledby="picture-heading" className={styles.section}>
      <h2 id="picture-heading">Profile picture</h2>
      <div className={styles.upload}>
        <Avatar
          avatar={user.avatar}
          picture={user.pictureUrl}
          name={user.displayName}
          size={64}
          label="Your picture"
        />
        <div className={styles.uploadActions}>
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="visually-hidden"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => void choose(e)}
          />
          <Button
            id={uploadId}
            variant="secondary"
            loading={preparing || upload.isPending}
            keepFocusWhileLoading
            aria-disabled={busy || undefined}
            onClick={() => !busy && fileInput.current?.click()}
          >
            Upload a picture
          </Button>
          {user.pictureUrl && (
            <Button
              variant="ghost"
              loading={remove.isPending}
              keepFocusWhileLoading
              aria-disabled={busy || undefined}
              onClick={() =>
                !busy &&
                remove.mutate(undefined, {
                  // The button goes with the picture: focus the upload button, not the page.
                  onSuccess: () => document.getElementById(uploadId)?.focus(),
                })
              }
            >
              Remove it
            </Button>
          )}
        </div>
      </div>
      <p className={styles.muted}>Or choose one of ours:</p>
      <fieldset className={styles.pictures}>
        <legend className="visually-hidden">Choose one of our pictures</legend>
        {choices.map((choice) => {
          const label = choice ? avatarName(choice) : 'Your initial'
          return (
            <label key={choice ?? 'initial'} className={styles.picture}>
              <input
                type="radio"
                name={name}
                checked={shown === choice}
                aria-disabled={fileBusy || undefined}
                onChange={() => pick(choice)}
              />
              <Avatar avatar={choice} name={user.displayName} size={48} />
              <span className="visually-hidden">{label}</span>
            </label>
          )
        })}
      </fieldset>
      <output className={styles.muted}>
        {saved && !error ? 'Saved.' : 'Only you see your picture.'}
      </output>
      {error && <Alert tone="danger">{error}</Alert>}
    </section>
  )
}

/** One switch in "What you see while you learn": a checkbox, its label and a line on what it
 * does, read with it (`aria-describedby`, with the group's note on where it is kept). */
function Setting({
  label,
  about,
  checked,
  onChange,
  disabled,
  note,
}: {
  label: string
  about: ReactNode
  checked: boolean
  onChange: (on: boolean) => void
  disabled?: boolean
  note?: string
}) {
  const id = useId()
  return (
    <div className={styles.setting}>
      <div className={styles.toggle}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          aria-describedby={note ? `${id}-about ${note}` : `${id}-about`}
          onChange={(e) => onChange(e.target.checked)}
        />
        <label htmlFor={id}>{label}</label>
      </div>
      <p id={`${id}-about`} className={styles.muted}>
        {about}
      </p>
    </div>
  )
}

/**
 * What you see while you learn (#214): one switch for each motivational element, all on by
 * default, because some students find them demotivating (Self-Determination Theory: autonomy).
 *
 * - Points and badges (FR-9.5): kept on the account, the same setting as on the badges page. The
 *   module medals follow it, so they have no switch of their own.
 * - Skill profile, progress panel, confetti and encouraging comments: kept on this device, per
 *   student (features/progress/preferences.ts).
 *
 * The mastery report and quick check results are never hidden.
 */
function LearningSettings() {
  const rewards = useRewards()
  const settings = useRewardsSettings()
  const [confettiOn, setConfetti] = useConfettiSetting()
  const [comments, setComments] = usePreference('comments')
  const [profile, setProfile] = usePreference('skillProfile')
  const [panel, setPanel] = usePreference('progressPanel')
  const deviceNote = useId()
  const heading = useRef<HTMLHeadingElement>(null)
  const { hash } = useLocation()
  // Linked from "… hidden. Turn it back on in your profile" (#214): straight to this group.
  useEffect(() => {
    if (hash !== '#what-you-see') return
    heading.current?.scrollIntoView?.({ block: 'start' })
    heading.current?.focus()
  }, [hash])
  return (
    <section
      id="what-you-see"
      aria-labelledby="learning-settings-heading"
      className={styles.section}
    >
      <h2 id="learning-settings-heading" ref={heading} tabIndex={-1}>
        What you see while you learn
      </h2>
      <p className={styles.muted}>
        Turn off anything you would rather not see. Your mastery report and your quick check results
        are always shown.
      </p>
      <Setting
        label="Points and badges"
        about="Points for each answer, badges and module medals. Off, you still earn them, and they come back when you turn this on."
        checked={rewards.data ? !rewards.data.hideRewards : true}
        disabled={rewards.isPending || settings.isPending}
        onChange={(on) => settings.mutate({ hideRewards: !on })}
      />
      {settings.isError && <Alert tone="danger">{settings.error.message}</Alert>}
      <Setting
        label="Skill profile"
        about="The chart of the eight objectives on your home page, and the list of them in the progress panel."
        checked={profile}
        onChange={setProfile}
        note={deviceNote}
      />
      <Setting
        label="Progress panel beside lessons"
        about="Your progress in the module, the activities to look at again and your latest badges, beside a lesson or under it on a phone. Off, the lesson takes the full width."
        checked={panel}
        onChange={setPanel}
        note={deviceNote}
      />
      <Setting
        label="Confetti when you get something right"
        about={
          <>
            A short burst for a right answer, and a bigger one when you finish a module or are ready
            for the lecture. Never during the mastery check.
            {prefersReducedMotion() &&
              ' Your device asks for reduced motion, so it stays off anyway.'}
          </>
        }
        checked={confettiOn}
        onChange={setConfetti}
        note={deviceNote}
      />
      <Setting
        label="Encouraging comments"
        about="A short line under a right answer, and a word on how far you have come. Off, you see only the explanation of why the answer is right."
        checked={comments}
        onChange={setComments}
        note={deviceNote}
      />
      <p id={deviceNote} className={styles.muted}>
        Points and badges are kept with your account. The other four are kept on this device, for
        you only: on a shared computer they don&apos;t change anyone else&apos;s, and on another
        device they start on again.
      </p>
    </section>
  )
}

type Field = 'current' | 'next' | 'confirm'
const order: Field[] = ['current', 'next', 'confirm']
const ids: Record<Field, string> = {
  current: 'profile-current-password',
  next: 'profile-new-password',
  confirm: 'profile-confirm-password',
}
const rulesId = 'profile-password-rules'
const WRONG_CURRENT = 'Your current password is not right.'

/** Change the password (FR-1.5): the current one, then a new one that meets the rules, twice. */
function Password({ user }: { user: User }) {
  const change = useChangePassword()
  const [values, setValues] = useState<Record<Field, string>>({
    current: '',
    next: '',
    confirm: '',
  })
  const [errors, setErrors] = useState<FieldErrors<Field>>({})
  const set = (field: Field) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [field]: e.target.value }))

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const found: FieldErrors<Field> = {
      current: values.current ? undefined : 'Enter your current password.',
      next: newPasswordError(values.next, user.email, user.displayName),
      confirm: values.confirm === values.next ? undefined : "The two new passwords don't match.",
    }
    setErrors(found)
    if (order.some((f) => found[f])) {
      focusFirstError(order, found, ids)
      return
    }
    change.mutate(
      { currentPassword: values.current, newPassword: values.next },
      {
        onSuccess: () => setValues({ current: '', next: '', confirm: '' }),
        onError: (error) => {
          if (!(error instanceof ApiError) || error.status !== 400) return
          const problem: FieldErrors<Field> =
            error.message === WRONG_CURRENT ? { current: error.message } : { next: error.message }
          setErrors(problem)
          focusFirstError(order, problem, ids)
        },
      },
    )
  }

  const general =
    change.error && !(change.error instanceof ApiError && change.error.status === 400)
      ? change.error.message
      : undefined

  return (
    <section aria-labelledby="password-heading" className={styles.section}>
      <h2 id="password-heading">Change your password</h2>
      {change.isSuccess && (
        <Alert tone="success" title="Password changed">
          You're still logged in here. Anywhere else you were logged in, you'll need the new
          password.
        </Alert>
      )}
      {general && <Alert tone="danger">{general}</Alert>}
      <form onSubmit={onSubmit} noValidate className={styles.form}>
        <TextField
          id={ids.current}
          label="Current password"
          type="password"
          autoComplete="current-password"
          value={values.current}
          onChange={set('current')}
          error={errors.current}
        />
        <TextField
          id={ids.next}
          label="New password"
          type="password"
          autoComplete="new-password"
          value={values.next}
          onChange={set('next')}
          error={errors.next}
          aria-describedby={errors.next ? `${ids.next}-message ${rulesId}` : rulesId}
        />
        <PasswordChecklist
          id={rulesId}
          password={values.next}
          email={user.email}
          name={user.displayName}
        />
        <TextField
          id={ids.confirm}
          label="New password again"
          type="password"
          autoComplete="new-password"
          value={values.confirm}
          onChange={set('confirm')}
          error={errors.confirm}
        />
        <Button type="submit" loading={change.isPending}>
          Change password
        </Button>
      </form>
    </section>
  )
}

/**
 * /profile — the student's own profile (#111, FR-1.5 to FR-1.7): their progress, their picture,
 * whether points and badges show, and changing their password. Reached from the account menu.
 */
export function ProfilePage() {
  const { data: user, isPending } = useCurrentUser()
  if (isPending || !user) return <Spinner label="Loading your profile" />
  return (
    <>
      <div className={styles.heading}>
        <Avatar avatar={user.avatar} picture={user.pictureUrl} name={user.displayName} size={72} />
        <div>
          <h1>{user.displayName}</h1>
          <p className={styles.muted}>{user.email}</p>
        </div>
      </div>
      <Stats />
      <Picture user={user} />
      <LearningSettings />
      <Password user={user} />
    </>
  )
}
