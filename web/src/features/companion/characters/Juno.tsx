// Juno, a friendly robot: a rounded head with a soft face plate, honey ear lights and an
// antenna that lights when it is pleased. Pleased: both arms up. Encouraging: head tilted, one
// hand raised, open palm.
import { Eyes, Frame, Mouth, type CharacterProps } from './parts.tsx'

const ARMS = {
  neutral: [
    [18, 49, 13, 62],
    [46, 49, 51, 62],
  ],
  pleased: [
    [18, 49, 8, 34],
    [46, 49, 56, 34],
  ],
  encouraging: [
    [18, 49, 13, 62],
    [46, 49, 57, 38],
  ],
} as const

export function Juno({ pose, size, className }: CharacterProps) {
  const tilt = pose === 'encouraging' ? 7 : 0
  const lit = pose === 'pleased'
  return (
    <Frame size={size} className={className}>
      <g fill="none" stroke="var(--cmp-edge)" strokeWidth={4.5} strokeLinecap="round">
        {ARMS[pose].map(([x1, y1, x2, y2]) => (
          <line key={x2} x1={x1} y1={y1} x2={x2} y2={y2} />
        ))}
      </g>
      <g fill="var(--cmp-paper)" stroke="var(--cmp-edge)" strokeWidth={1.4}>
        {ARMS[pose].map(([, , x, y]) => (
          <circle key={x} cx={x} cy={y} r={3} />
        ))}
      </g>
      <path
        d="M17 64L19 47Q21 43 32 43Q43 43 45 47L47 64Z"
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={1.6}
      />
      <circle cx={32} cy={54} r={3} fill={lit ? 'var(--cmp-honey)' : 'var(--cmp-off)'} />
      <rect x={28} y={38} width={8} height={6} fill="var(--cmp-edge)" />
      <g transform={`rotate(${tilt} 32 26)`}>
        <line x1={32} y1={11} x2={32} y2={5} stroke="var(--cmp-edge)" strokeWidth={2} />
        <circle
          cx={32}
          cy={4.5}
          r={2.8}
          fill={lit ? 'var(--cmp-honey)' : 'var(--cmp-off)'}
          stroke="var(--cmp-edge)"
          strokeWidth={1}
        />
        {lit && (
          <g stroke="var(--cmp-honey)" strokeWidth={1.4} strokeLinecap="round">
            <path d="M26 3.5l-2.5-1" />
            <path d="M38 3.5l2.5-1" />
          </g>
        )}
        <circle
          cx={13}
          cy={25}
          r={3.2}
          fill="var(--cmp-honey)"
          stroke="var(--cmp-honey-edge)"
          strokeWidth={1}
        />
        <circle
          cx={51}
          cy={25}
          r={3.2}
          fill="var(--cmp-honey)"
          stroke="var(--cmp-honey-edge)"
          strokeWidth={1}
        />
        <rect
          x={14}
          y={10}
          width={36}
          height={30}
          rx={13}
          fill="var(--cmp-blue)"
          stroke="var(--cmp-edge)"
          strokeWidth={1.8}
        />
        <rect x={18.5} y={15.5} width={27} height={19} rx={9} fill="var(--cmp-soft)" />
        <Eyes pose={pose} x1={26} x2={38} y={23.5} color="var(--cmp-on-soft)" r={2.1} />
        <Mouth pose={pose} x={32} y={29.5} w={6.5} color="var(--cmp-on-soft)" />
      </g>
    </Frame>
  )
}
