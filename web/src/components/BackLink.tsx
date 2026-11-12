import { Link, useLocation } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import type { BackState } from './backState.ts'

function isBackState(state: unknown): state is BackState {
  const s = state as Partial<BackState> | null
  return (
    typeof s?.backTo === 'string' && s.backTo.startsWith('/') && typeof s.backLabel === 'string'
  )
}

/** A link back to the page this one was opened from, or to `fallback` when there is none (the
 * page was opened from an address, a bookmark or a refresh). Renders nothing with neither. */
export function BackLink({ fallback }: { fallback?: BackState }) {
  const state: unknown = useLocation().state
  const back = isBackState(state) ? state : fallback
  if (!back) return null
  return (
    <Link to={back.backTo} className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
      ← {back.backLabel}
    </Link>
  )
}
