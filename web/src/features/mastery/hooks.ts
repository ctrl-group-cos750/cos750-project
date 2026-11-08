import { useQuery } from '@tanstack/react-query'
import { fetchReport } from './mastery.api.ts'

export const reportKey = ['mastery-report'] as const

/** The student's mastery report. It only changes when they answer a mastery item, so a page
 * that submits one should invalidate `reportKey`. */
export function useReport() {
  return useQuery({ queryKey: reportKey, queryFn: fetchReport })
}
