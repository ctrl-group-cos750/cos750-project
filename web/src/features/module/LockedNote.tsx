import { Fragment } from 'react'
import { Link } from 'react-router'
import type { UnlockNeeds } from './unlock.ts'

/**
 * How to open a locked module (#214): the rule in one sentence, then each module still to do as
 * a link to it. Plain text, so it is read with the module on the map (`aria-describedby`) and on
 * the module's own page when it is opened by its address.
 */
export function LockedNote({
  needs,
  id,
  className,
}: {
  needs: UnlockNeeds
  id?: string
  className?: string
}) {
  const { from, to, remaining } = needs
  return (
    <p id={id} className={className}>
      Opens once each of modules {from} to {to} is finished or you passed its quick check.
      {remaining.length > 0 && (
        <>
          {' '}
          Still to do:{' '}
          {remaining.map((m, index) => (
            <Fragment key={m.id}>
              {index > 0 && ', '}
              <Link to={`/modules/${m.id}`}>module {m.number}</Link>
            </Fragment>
          ))}
          .
        </>
      )}
    </p>
  )
}
