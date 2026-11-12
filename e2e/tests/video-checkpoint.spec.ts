import { CHECKPOINT, createVideo, expect, seekPastCheckpoint, test } from './fixtures'

// A narrated video with a checkpoint (FR-3; ID document §7.3). The video is made through the
// staff API for each test, as staff make one on the Videos page (e2e/media/), so a fresh stack
// needs no videos, its checkpoint is the test's own, and no other test has passed it.

const option = (id: string) => CHECKPOINT.question.options.find((o) => o.id === id)?.label ?? ''

test('the video stops at its checkpoint, takes a wrong answer, gives the hints in order, then resumes', async ({
  page,
  student,
  staff,
}, testInfo) => {
  void student
  const videoId = await createVideo(staff, `E2E: ${testInfo.title}`)
  await page.goto(`/videos/${videoId}`)
  await expect(page.getByRole('heading', { name: 'Transcript' })).toBeVisible()

  // Skipping ahead isn't allowed: the player goes back to the checkpoint and asks (FR-3.3).
  await seekPastCheckpoint(page)
  const video = page.locator('video')
  expect(await video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeCloseTo(
    CHECKPOINT.atSeconds,
  )
  expect(await video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true)

  // Play while the question is open doesn't get past it.
  await video.evaluate((v: HTMLVideoElement) => {
    v.muted = true
    return v.play().catch(() => undefined)
  })
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true)
  expect(await video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeLessThan(
    CHECKPOINT.atSeconds + 0.5,
  )

  // A wrong answer gets the feedback written for that option (FR-4.2).
  const checkpoint = page.getByRole('region', { name: 'Checkpoint' })
  await expect(checkpoint.getByText('Not quite')).toHaveCount(0)
  await checkpoint.getByRole('radio', { name: option('deepest') }).check()
  await checkpoint.getByRole('button', { name: 'Check answer' }).click()
  await expect(checkpoint.getByText('Not quite')).toBeVisible()
  await expect(checkpoint.getByText(CHECKPOINT.question.feedback.deepest)).toBeVisible()

  // The hint ladder, one level at a time, with a warning before hint 3 (FR-4.4, ID document §7.4).
  const nextHint = checkpoint.getByRole('button', { name: 'Show next hint' })
  await expect(checkpoint.getByText(CHECKPOINT.hints[0].body)).toHaveCount(0)
  await nextHint.click()
  await expect(checkpoint.getByText(CHECKPOINT.hints[0].body)).toBeVisible()
  await expect(checkpoint.getByText(CHECKPOINT.hints[1].body)).toHaveCount(0)
  await nextHint.click()
  await expect(checkpoint.getByText(CHECKPOINT.hints[1].body)).toBeVisible()
  await nextHint.click()
  await expect(checkpoint.getByText('The next hint gives a lot away')).toBeVisible()
  await expect(checkpoint.getByText(CHECKPOINT.hints[2].body)).toHaveCount(0)
  await nextHint.click()
  await expect(checkpoint.getByText(CHECKPOINT.hints[2].body)).toBeVisible()

  await checkpoint.getByRole('radio', { name: option('start') }).check()
  await checkpoint.getByRole('button', { name: 'Check answer' }).click()
  await expect(checkpoint.getByText('Correct', { exact: true })).toBeVisible()

  await video.evaluate((v: HTMLVideoElement) => {
    v.muted = true // a muted video may play without a user gesture
  })
  await checkpoint.getByRole('button', { name: 'Resume video' }).click()
  await expect(page.getByRole('heading', { name: 'Checkpoint' })).toHaveCount(0)
})

test('a checkpoint passed before does not stop the student again (FR-3.5)', async ({
  page,
  student,
  staff,
}, testInfo) => {
  void student
  const videoId = await createVideo(staff, `E2E: ${testInfo.title}`)
  await page.goto(`/videos/${videoId}`)
  await seekPastCheckpoint(page)
  const checkpoint = page.getByRole('region', { name: 'Checkpoint' })
  await checkpoint.getByRole('radio', { name: option('start') }).check()
  await checkpoint.getByRole('button', { name: 'Check answer' }).click()
  await expect(checkpoint.getByText('Correct', { exact: true })).toBeVisible()

  await page.reload()
  const video = page.locator('video')
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState))
    .toBeGreaterThanOrEqual(1)
  await video.evaluate((v: HTMLVideoElement) => {
    v.currentTime = 6
  })
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(5)
  // Give the player the time it took to snap back above, then check it didn't.
  await page.waitForTimeout(500)
  await expect(page.getByRole('heading', { name: 'Checkpoint' })).toHaveCount(0)
  expect(await video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(5)
})
