import type { ReactNode } from 'react'
import type { AvatarId } from './avatars.ts'
import styles from './Avatar.module.css'

const dot = (x: number, y: number, key?: string) => <circle key={key} cx={x} cy={y} r={3.2} />
const line = (x1: number, y1: number, x2: number, y2: number, key?: string) => (
  <line key={key} x1={x1} y1={y1} x2={x2} y2={y2} />
)

/** Each picture as SVG on a 40 × 40 grid: graph and BFS shapes, so none looks like a person. */
const DRAWINGS: Record<AvatarId, ReactNode> = {
  vertex: <circle cx={20} cy={20} r={7} />,
  edge: (
    <>
      {line(11, 26, 29, 14)}
      {dot(11, 26)}
      {dot(29, 14)}
    </>
  ),
  path: (
    <>
      {line(8, 28, 16, 14)}
      {line(16, 14, 24, 26)}
      {line(24, 26, 32, 12)}
      {[dot(8, 28, 'a'), dot(16, 14, 'b'), dot(24, 26, 'c'), dot(32, 12, 'd')]}
    </>
  ),
  cycle: (
    <>
      {line(20, 9, 31, 26)}
      {line(31, 26, 9, 26)}
      {line(9, 26, 20, 9)}
      {[dot(20, 9, 'a'), dot(31, 26, 'b'), dot(9, 26, 'c')]}
    </>
  ),
  tree: (
    <>
      {line(20, 9, 12, 20)}
      {line(20, 9, 28, 20)}
      {line(12, 20, 8, 31)}
      {line(12, 20, 16, 31)}
      {line(28, 20, 32, 31)}
      {[dot(20, 9, 'a'), dot(12, 20, 'b'), dot(28, 20, 'c')]}
      {[dot(8, 31, 'd'), dot(16, 31, 'e'), dot(32, 31, 'f')]}
    </>
  ),
  star: (
    <>
      {[
        line(20, 20, 20, 8, 'a'),
        line(20, 20, 31, 16, 'b'),
        line(20, 20, 27, 31, 'c'),
        line(20, 20, 13, 31, 'd'),
        line(20, 20, 9, 16, 'e'),
      ]}
      {[dot(20, 20, 'o'), dot(20, 8, 'a'), dot(31, 16, 'b'), dot(27, 31, 'c'), dot(13, 31, 'd')]}
      {dot(9, 16, 'e')}
    </>
  ),
  grid: (
    <>
      {[line(11, 11, 29, 11, 'a'), line(11, 29, 29, 29, 'b')]}
      {[line(11, 11, 11, 29, 'c'), line(29, 11, 29, 29, 'd')]}
      {[dot(11, 11, 'a'), dot(29, 11, 'b'), dot(11, 29, 'c'), dot(29, 29, 'd')]}
    </>
  ),
  queue: (
    <>
      {[8, 17, 26].map((x) => (
        <rect key={x} x={x} y={14} width={7} height={12} rx={1.5} />
      ))}
      {line(5, 33, 35, 33)}
    </>
  ),
}

export type AvatarProps = {
  avatar: AvatarId | null | undefined
  /** Shown as an initial when no picture is chosen. */
  name: string
  size?: number
  /** Decorative next to the name (the default); give a label when it stands alone. */
  label?: string
}

/** A student's profile picture, or their initial if they haven't chosen one. Only they see it. */
export function Avatar({ avatar, name, size = 32, label }: AvatarProps) {
  const a11y = label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true }
  if (!avatar) {
    return (
      <span
        className={styles.initial}
        style={{ width: size, height: size, fontSize: size * 0.45 }}
        {...a11y}
      >
        {name.trim().charAt(0).toUpperCase() || '?'}
      </span>
    )
  }
  return (
    <svg className={styles.avatar} width={size} height={size} viewBox="0 0 40 40" {...a11y}>
      <circle className={styles.ground} cx={20} cy={20} r={20} />
      <g className={styles.drawing}>{DRAWINGS[avatar]}</g>
    </svg>
  )
}
