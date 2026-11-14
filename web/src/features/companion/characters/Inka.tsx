// Inka, a calm octopus whose arms are edges, each reaching a honey neighbour vertex.
// Neutral: arms resting. Pleased: two arms lift their vertices up. Encouraging: one arm reaches
// out and offers a vertex, the next one to visit.
import { Eyes, Frame, Mouth, type CharacterProps } from './parts.tsx'

type Arm = [number, number, number, number, number, number] // start x, start y, control x/y, end x/y

const ARMS: Record<CharacterProps['pose'], Arm[]> = {
  neutral: [
    [21, 34, 12, 40, 7, 53],
    [25, 36, 20, 50, 16, 59],
    [30, 37, 28, 52, 27, 60],
    [34, 37, 36, 52, 37, 60],
    [39, 36, 44, 50, 48, 59],
    [43, 34, 52, 40, 57, 53],
  ],
  pleased: [
    [21, 32, 8, 32, 7, 15],
    [25, 36, 20, 50, 16, 59],
    [30, 37, 28, 52, 27, 60],
    [34, 37, 36, 52, 37, 60],
    [39, 36, 44, 50, 48, 59],
    [43, 32, 56, 32, 57, 15],
  ],
  encouraging: [
    [21, 34, 12, 40, 7, 53],
    [25, 36, 20, 50, 16, 59],
    [30, 37, 28, 52, 27, 60],
    [34, 37, 36, 52, 37, 60],
    [39, 36, 44, 50, 48, 59],
    [43, 32, 54, 38, 59, 29],
  ],
}

export function Inka({ pose, size, className }: CharacterProps) {
  return (
    <Frame size={size} className={className}>
      <g fill="none" stroke="var(--cmp-blue)" strokeWidth={3.6} strokeLinecap="round">
        {ARMS[pose].map(([x1, y1, cx, cy, x2, y2]) => (
          <path key={`${x2}-${y2}`} d={`M${x1} ${y1}Q${cx} ${cy} ${x2} ${y2}`} />
        ))}
      </g>
      <g fill="var(--cmp-honey)" stroke="var(--cmp-honey-edge)" strokeWidth={1.4}>
        {ARMS[pose].map(([, , , , x, y]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={3.4} />
        ))}
      </g>
      <path
        d="M17 27Q17 6 32 6Q47 6 47 27Q47 38 32 38Q17 38 17 27Z"
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={1.8}
      />
      {/* A calm sheen on the head */}
      <path
        d="M23 15Q26 10 31 9.5"
        fill="none"
        stroke="var(--cmp-paper)"
        strokeOpacity={0.45}
        strokeWidth={1.8}
        strokeLinecap="round"
      />
      <Eyes pose={pose} x1={26.5} x2={37.5} y={24} color="var(--cmp-paper)" r={2.1} />
      <Mouth pose={pose} x={32} y={30.5} w={7} color="var(--cmp-paper)" fill="var(--cmp-edge)" />
    </Frame>
  )
}
