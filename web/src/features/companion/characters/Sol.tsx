// Sol, a young scout with a lantern: BFS lights up the graph one ring at a time.
// A blue explorer's hat with a honey band. Neutral: lantern held low. Pleased: lantern raised, its
// light wider. Encouraging: head tilted, lantern held out to light your next step.
import { Eyes, Frame, Mouth, type CharacterProps } from './parts.tsx'

function Lantern({ x, y, glow }: { x: number; y: number; glow: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle cx={0} cy={2} r={glow} fill="var(--cmp-honey)" opacity={0.28} />
      <path d="M-3 -6Q0 -10 3 -6" fill="none" stroke="var(--cmp-edge)" strokeWidth={1.4} />
      <rect x={-4} y={-6} width={8} height={2.4} rx={1} fill="var(--cmp-edge)" />
      <rect
        x={-3.5}
        y={-3.6}
        width={7}
        height={8.5}
        rx={2}
        fill="var(--cmp-honey)"
        stroke="var(--cmp-honey-edge)"
        strokeWidth={1.1}
      />
      <rect x={-4} y={4.6} width={8} height={2.2} rx={1} fill="var(--cmp-edge)" />
    </g>
  )
}

const ARM = {
  neutral: { d: 'M42 51Q48 56 51 55', lantern: [52, 57], glow: 6 },
  pleased: { d: 'M42 50Q52 44 53 30', lantern: [53, 22], glow: 9 },
  encouraging: { d: 'M42 51Q50 50 53 44', lantern: [55, 45], glow: 7.5 },
} as const

export function Sol({ pose, size, className }: CharacterProps) {
  const tilt = pose === 'encouraging' ? -6 : 0
  const arm = ARM[pose]
  return (
    <Frame size={size} className={className}>
      <path
        d="M10 64Q12 48 29 46Q46 48 48 64Z"
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={1.6}
      />
      <path
        d="M21 47L29 53L37 47"
        fill="none"
        stroke="var(--cmp-honey)"
        strokeWidth={3}
        strokeLinejoin="round"
      />
      <line x1={18} y1={50} x2={21} y2={64} stroke="var(--cmp-edge)" strokeWidth={2.2} />
      <rect x={25.5} y={39} width={7} height={8} fill="var(--cmp-skin)" />
      <g transform={`rotate(${tilt} 29 30)`}>
        <path d="M17 30Q16 40 21 41L22 30Z M41 30Q42 40 37 41L36 30Z" fill="var(--cmp-hair)" />
        <circle cx={29} cy={30} r={11.5} fill="var(--cmp-skin)" />
        <path
          d="M17.5 26Q19 19 29 19Q39 19 40.5 26Q34 23 29 23.5Q22 23 17.5 26Z"
          fill="var(--cmp-hair)"
        />
        <Eyes pose={pose} x1={24.5} x2={33.5} y={30.5} color="var(--cmp-ink)" r={1.7} />
        <Mouth pose={pose} x={29} y={36} w={6} color="var(--cmp-ink)" fill="var(--cmp-paper)" />
        {/* Hat */}
        <ellipse cx={29} cy={20.5} rx={17} ry={3.6} fill="var(--cmp-edge)" />
        <path
          d="M18.5 20.5Q19 7 29 7Q39 7 39.5 20.5Z"
          fill="var(--cmp-blue)"
          stroke="var(--cmp-edge)"
          strokeWidth={1.4}
        />
        <rect x={19} y={16} width={20} height={3} fill="var(--cmp-honey)" />
      </g>
      <path d={arm.d} fill="none" stroke="var(--cmp-blue)" strokeWidth={5} strokeLinecap="round" />
      <path
        d={arm.d}
        fill="none"
        stroke="var(--cmp-edge)"
        strokeWidth={1}
        strokeLinecap="round"
        opacity={0.5}
      />
      <Lantern x={arm.lantern[0]} y={arm.lantern[1]} glow={arm.glow} />
    </Frame>
  )
}
