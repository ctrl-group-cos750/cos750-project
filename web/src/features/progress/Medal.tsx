import { medalText } from './medals.ts'
import type { Medal as MedalTier } from './skills.api.ts'
import styles from './progress.module.css'

/**
 * A module medal: a disc on a ribbon. The tiers differ in shape as well as colour (NFR-A2): gold
 * carries a star, silver a ring, bronze is plain. Named for screen readers by `label`, or by its
 * tier and rule.
 */
export function Medal({
  tier,
  size = 28,
  label,
}: {
  tier: MedalTier
  size?: number
  label?: string
}) {
  return (
    <svg
      className={`${styles.medal} ${styles[tier]}`}
      viewBox="0 0 32 32"
      width={size}
      height={size}
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role -- one picture with a name
      role="img"
      aria-label={label ?? medalText(tier)}
    >
      <title>{label ?? medalText(tier)}</title>
      <path className={styles.ribbon} d="M10 2h5l3 9h-5zM22 2h-5l-3 9h5z" />
      <circle className={styles.disc} cx="16" cy="20" r="10" />
      {tier === 'silver' && <circle className={styles.mark} cx="16" cy="20" r="6" fill="none" />}
      {tier === 'gold' && (
        <polygon
          className={styles.star}
          points="16,14 17.8,18.2 22.2,18.5 18.8,21.3 19.9,25.6 16,23.3 12.1,25.6 13.2,21.3 9.8,18.5 14.2,18.2"
        />
      )}
    </svg>
  )
}
