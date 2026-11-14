// The face parts every companion character shares (#214), so the three poses read the same way
// whichever character is chosen: neutral (open eyes, small smile), pleased (eyes closed in a smile,
// open smile) and encouraging (open eyes, brows lifted, a wider soft smile).
import type { ReactNode, SVGProps } from 'react'

export type Pose = 'neutral' | 'pleased' | 'encouraging'

export type CharacterProps = { pose: Pose; size?: number; className?: string }

/** The SVG frame: 64 × 64 units, decorative (the bubble carries the words). */
export function Frame({
  size = 64,
  className,
  children,
  ...rest
}: { size?: number; className?: string; children: ReactNode } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  )
}

/** Two eyes centred on x1 and x2 at height y. */
export function Eyes({
  pose,
  x1,
  x2,
  y,
  color,
  r = 2.2,
}: {
  pose: Pose
  x1: number
  x2: number
  y: number
  color: string
  r?: number
}) {
  if (pose === 'pleased')
    return (
      <g fill="none" stroke={color} strokeWidth={r * 0.95} strokeLinecap="round">
        <path
          d={`M${x1 - r * 1.25} ${y + r * 0.5}Q${x1} ${y - r * 1.5} ${x1 + r * 1.25} ${y + r * 0.5}`}
        />
        <path
          d={`M${x2 - r * 1.25} ${y + r * 0.5}Q${x2} ${y - r * 1.5} ${x2 + r * 1.25} ${y + r * 0.5}`}
        />
      </g>
    )
  return (
    <g fill={color}>
      <ellipse cx={x1} cy={y} rx={r} ry={r * 1.25} />
      <ellipse cx={x2} cy={y} rx={r} ry={r * 1.25} />
      {pose === 'encouraging' && (
        <g fill="none" stroke={color} strokeWidth={r * 0.7} strokeLinecap="round">
          {/* Brows lifted in soft arcs: attentive, on your side. */}
          <path
            d={`M${x1 - r * 1.3} ${y - r * 2}Q${x1} ${y - r * 3} ${x1 + r * 1.3} ${y - r * 2}`}
          />
          <path
            d={`M${x2 - r * 1.3} ${y - r * 2}Q${x2} ${y - r * 3} ${x2 + r * 1.3} ${y - r * 2}`}
          />
        </g>
      )}
    </g>
  )
}

/** A mouth centred on x at height y, w wide. */
export function Mouth({
  pose,
  x,
  y,
  w,
  color,
  fill,
}: {
  pose: Pose
  x: number
  y: number
  w: number
  color: string
  /** The inside of the open (pleased) smile. */
  fill?: string
}) {
  const h = w / 2
  if (pose === 'pleased')
    return (
      <path
        d={`M${x - h} ${y - 0.5}Q${x} ${y + w * 0.75} ${x + h} ${y - 0.5}Z`}
        fill={fill ?? color}
        stroke={color}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />
    )
  if (pose === 'encouraging')
    return (
      <path
        d={`M${x - h} ${y - 0.4}Q${x} ${y + w * 0.45} ${x + h} ${y - 0.4}`}
        fill="none"
        stroke={color}
        strokeWidth={1.9}
        strokeLinecap="round"
      />
    )
  return (
    <path
      d={`M${x - h * 0.8} ${y}Q${x} ${y + w * 0.35} ${x + h * 0.8} ${y}`}
      fill="none"
      stroke={color}
      strokeWidth={1.9}
      strokeLinecap="round"
    />
  )
}
