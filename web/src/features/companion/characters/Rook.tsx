// Rook, a raccoon tinkerer with a tool belt: fixes bugs, likes taking things apart to see
// how they work. Neutral: wrench at the belt. Pleased: wrench raised. Encouraging: head tilted,
// a paw held up open, "nearly fixed".
import { Eyes, Frame, Mouth, type CharacterProps } from './parts.tsx'

function Wrench({ x, y, angle }: { x: number; y: number; angle: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${angle})`}>
      <rect
        x={-1.6}
        y={0}
        width={3.2}
        height={12}
        rx={1.4}
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={0.8}
      />
      <path
        d="M-4 -4Q-4.5 1 0 1.5Q4.5 1 4 -4L2 -4L2 -1L-2 -1L-2 -4Z"
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={0.8}
        strokeLinejoin="round"
      />
    </g>
  )
}

export function Rook({ pose, size, className }: CharacterProps) {
  const tilt = pose === 'encouraging' ? 6 : 0
  return (
    <Frame size={size} className={className}>
      {/* Body, apron and tool belt */}
      <path
        d="M11 64Q13 46 32 44Q51 46 53 64Z"
        fill="var(--cmp-grey)"
        stroke="var(--cmp-grey-dark)"
        strokeWidth={1.4}
      />
      <path d="M24 46Q32 49 40 46L41 64L23 64Z" fill="var(--cmp-paper)" opacity={0.85} />
      <rect
        x={12}
        y={56}
        width={40}
        height={5}
        fill="var(--cmp-honey)"
        stroke="var(--cmp-honey-edge)"
        strokeWidth={1}
      />
      <rect
        x={29.5}
        y={55.5}
        width={5}
        height={6}
        rx={1}
        fill="none"
        stroke="var(--cmp-honey-edge)"
        strokeWidth={1.2}
      />
      {pose === 'neutral' && <Wrench x={45} y={51} angle={0} />}
      {pose === 'pleased' && (
        <>
          <path
            d="M47 52Q55 46 55 36"
            fill="none"
            stroke="var(--cmp-grey)"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <Wrench x={56} y={32} angle={20} />
          <circle cx={55} cy={35} r={2.8} fill="var(--cmp-grey-dark)" />
        </>
      )}
      {pose === 'encouraging' && (
        <>
          <path
            d="M47 52Q55 48 56 40"
            fill="none"
            stroke="var(--cmp-grey)"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <circle cx={56} cy={37.5} r={3.6} fill="var(--cmp-grey-dark)" />
          <Wrench x={45} y={51} angle={0} />
        </>
      )}
      <g transform={`rotate(${tilt} 32 28)`}>
        {/* Ears */}
        <circle
          cx={17}
          cy={13}
          r={6.5}
          fill="var(--cmp-grey)"
          stroke="var(--cmp-grey-dark)"
          strokeWidth={1.4}
        />
        <circle
          cx={47}
          cy={13}
          r={6.5}
          fill="var(--cmp-grey)"
          stroke="var(--cmp-grey-dark)"
          strokeWidth={1.4}
        />
        <circle cx={17} cy={13} r={3} fill="var(--cmp-grey-dark)" />
        <circle cx={47} cy={13} r={3} fill="var(--cmp-grey-dark)" />
        <ellipse
          cx={32}
          cy={27}
          rx={19}
          ry={16}
          fill="var(--cmp-grey)"
          stroke="var(--cmp-grey-dark)"
          strokeWidth={1.4}
        />
        {/* The mask */}
        <path
          d="M13.5 25Q19 18 27 22Q32 24.5 37 22Q45 18 50.5 25Q47 33 38.5 30Q32 28 25.5 30Q17 33 13.5 25Z"
          fill="var(--cmp-grey-dark)"
        />
        <path d="M30 12L32 21L34 12Z" fill="var(--cmp-grey-dark)" />
        <Eyes pose={pose} x1={24} x2={40} y={25.5} color="var(--cmp-paper)" r={2.1} />
        <ellipse cx={32} cy={35} rx={8.5} ry={6.5} fill="var(--cmp-paper)" />
        <ellipse cx={32} cy={31.6} rx={2.4} ry={1.7} fill="var(--cmp-ink)" />
        <Mouth pose={pose} x={32} y={36} w={6} color="var(--cmp-ink)" />
      </g>
    </Frame>
  )
}
