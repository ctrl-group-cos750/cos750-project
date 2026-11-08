import { useQuery } from '@tanstack/react-query'
import { fetchReport, fetchReviewPath } from './mastery.api.ts'

export const reportKey = ['mastery-report'] as const

/** The student's mastery report. It only changes when they answer a mastery item, so a page
 * that submits one should invalidate `reportKey`. */
export function useReport() {
  return useQuery({ queryKey: reportKey, queryFn: fetchReport })
}

/** An objective's review path. Like the report, it changes only when the student answers. */
export function useReviewPath(objectiveId: number) {
  return useQuery({
    queryKey: [...reportKey, 'review', objectiveId],
    queryFn: () => fetchReviewPath(objectiveId),
    enabled: Number.isInteger(objectiveId) && objectiveId > 0,
  })
}
