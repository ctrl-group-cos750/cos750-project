import type { ReactElement } from 'react'
import { glyphs, hiddenGlyph, lockGlyph } from './AchievementGlyphs.tsx'
import type { Achievement, AchievementKind } from './achievements.ts'
import styles from './AchievementBadge.module.css'

/**
 * Where a student stands with a badge. Objective badges have three levels (#214): practised when
 * the objective is secure in the modules' practice, then the mastery results: bronze when it was
 * met with support (hint level 3 or 4), gold when it was met independently. Every other badge is
 * simply earned or not.
 */
export type AchievementState = 'locked' | 'earned' | 'practised' | 'bronze' | 'gold'

export type AchievementBadgeProps = {
  achievement: Achievement
  state: AchievementState
  /** Width and height in pixels. */
  size?: number
}

// The outline of each kind of badge on a 64-unit grid, and where its 24-unit picture sits
// (x, y, scale).
const frames: Record<AchievementKind, { shape: ReactElement; glyphAt: [number, number, number] }> =
  {
    objective: {
      shape: <polygon points="32,4 56.25,18 56.25,46 32,60 7.75,46 7.75,18" />,
      glyphAt: [17, 17, 1.25],
    },
    milestone: {
      shape: (
        <>
          <path d="M21 43l-5 18 8-3.5 4.5 5.5 3.5-14z M43 43l5 18-8-3.5-4.5 5.5-3.5-14z" />
          <circle cx="32" cy="28" r="23" />
        </>
      ),
      glyphAt: [17.6, 13.6, 1.2],
    },
    quest: {
      shape: <path d="M32 3.5l24 8.5v18.5c0 14-10 24-24 30-14-6-24-16-24-30V12z" />,
      glyphAt: [17.6, 16, 1.2],
    },
    hidden: {
      shape: <path d="M32 3l29 29-29 29L3 32z" />,
      glyphAt: [18.2, 18.2, 1.15],
    },
  }

// A five-point star on the hexagon's bottom corner, the gold tier's extra mark.
const goldStar = Array.from({ length: 10 }, (_, i) => {
  const radius = i % 2 === 0 ? 6.5 : 3
  const angle = (Math.PI / 5) * i - Math.PI / 2
  return `${(32 + radius * Math.cos(angle)).toFixed(2)},${(56.5 + radius * Math.sin(angle)).toFixed(2)}`
}).join(' ')

const tierText: Record<AchievementState, string> = {
  locked: 'not earned yet',
  earned: 'earned',
  practised: 'practised, secure in practice',
  bronze: 'bronze, met with support',
  gold: 'gold, met independently',
}

/**
 * A badge's picture, drawn from tokens so it follows the theme. Each state differs in shape as
 * well as colour (NFR-A2): practised is an outline with no fill, gold adds an inner outline and a
 * star, and locked badges are dashed, faded and carry a padlock. The hidden badge shows "?" until it is found.
 */
export function AchievementBadge({ achievement, state, size = 64 }: AchievementBadgeProps) {
  const { kind, glyph, name } = achievement
  const frame = frames[kind]
  const locked = state === 'locked'
  const secret = locked && kind === 'hidden'
  const colour = locked ? 'locked' : kind === 'objective' ? state : kind
  const label = secret ? 'Hidden badge, not found yet' : `${name}, ${tierText[state]}`

  return (
    <svg
      className={`${styles.badge} ${styles[colour]}`}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      // An inline SVG drawing needs role="img" to be read as one image with a name.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
      aria-label={label}
    >
      <g className={styles.frame}>{frame.shape}</g>
      {state === 'gold' && (
        <>
          <polygon
            className={styles.inner}
            points="32,9.5 51.5,20.75 51.5,43.25 32,54.5 12.5,43.25 12.5,20.75"
          />
          <polygon className={styles.star} points={goldStar} />
        </>
      )}
      <g
        className={styles.glyph}
        transform={`translate(${frame.glyphAt[0]} ${frame.glyphAt[1]}) scale(${frame.glyphAt[2]})`}
      >
        {secret ? hiddenGlyph : glyphs[glyph]}
      </g>
      {locked && !secret && (
        <g className={styles.lock} transform="translate(43 43) scale(0.75)">
          <circle cx="12" cy="12" r="12" />
          <g transform="translate(3.6 2.4) scale(0.7)">{lockGlyph}</g>
        </g>
      )}
    </svg>
  )
}
