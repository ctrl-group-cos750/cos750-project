// Rowan, a fox explorer with a map: BFS is exploring a map ring by ring. Honey fur, a
// Ctrl-blue jacket. Neutral: the map tucked at the side. Pleased: the map held up, found it.
// Encouraging: the map opened towards you, a dotted route and "you are here".
import { Eyes, Frame, Mouth, type CharacterProps } from './parts.tsx'

function Map({ x, y, open }: { x: number; y: number; open: boolean }) {
  const w = open ? 22 : 12
  const h = open ? 14 : 12
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect
        width={w}
        height={h}
        rx={1.5}
        fill="var(--cmp-paper)"
        stroke="var(--cmp-line)"
        strokeWidth={1.4}
      />
      {open ? (
        <>
          <line x1={w / 3} y1={0} x2={w / 3} y2={h} stroke="var(--cmp-soft)" strokeWidth={1} />
          <line
            x1={(2 * w) / 3}
            y1={0}
            x2={(2 * w) / 3}
            y2={h}
            stroke="var(--cmp-soft)"
            strokeWidth={1}
          />
          <path
            d={`M3 ${h - 3}Q8 3 13 8T19 4`}
            fill="none"
            stroke="#2470c9"
            strokeWidth={1.3}
            strokeDasharray="2 1.6"
          />
          <circle
            cx={19}
            cy={4}
            r={2}
            fill="var(--cmp-honey)"
            stroke="var(--cmp-honey-edge)"
            strokeWidth={0.8}
          />
        </>
      ) : (
        <>
          <line x1={w / 2} y1={0} x2={w / 2} y2={h} stroke="var(--cmp-soft)" strokeWidth={1} />
          <path
            d="M2.5 9Q5 3 9.5 4"
            fill="none"
            stroke="#2470c9"
            strokeWidth={1.2}
            strokeDasharray="1.8 1.4"
          />
        </>
      )}
    </g>
  )
}

export function Rowan({ pose, size, className }: CharacterProps) {
  const tilt = pose === 'encouraging' ? -6 : 0
  return (
    <Frame size={size} className={className}>
      {/* Jacket and shoulders */}
      <path
        d="M12 64Q13 49 32 47Q51 49 52 64Z"
        fill="var(--cmp-blue)"
        stroke="var(--cmp-edge)"
        strokeWidth={1.6}
      />
      <path d="M26 48L32 56L38 48" fill="var(--cmp-paper)" />
      <g transform={`rotate(${tilt} 32 30)`}>
        {/* Ears */}
        <g
          fill="var(--cmp-honey)"
          stroke="var(--cmp-honey-edge)"
          strokeWidth={1.5}
          strokeLinejoin="round"
        >
          <path d="M13 21L16 3L28 12Z" />
          <path d="M51 21L48 3L36 12Z" />
        </g>
        <g fill="var(--cmp-honey-edge)">
          <path d="M17 15L18 8L24 12.5Z" />
          <path d="M47 15L46 8L40 12.5Z" />
        </g>
        {/* Head, cheeks and muzzle */}
        <path
          d="M11 23Q11 11 32 11Q53 11 53 23Q53 33 43 40L32 47L21 40Q11 33 11 23Z"
          fill="var(--cmp-honey)"
          stroke="var(--cmp-honey-edge)"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        <path d="M17 31Q25 29 32 37Q39 29 47 31Q42 41 32 47Q22 41 17 31Z" fill="var(--cmp-paper)" />
        <Eyes pose={pose} x1={24.5} x2={39.5} y={25} color="var(--cmp-ink)" r={2} />
        <ellipse cx={32} cy={37.5} rx={2.6} ry={1.9} fill="var(--cmp-ink)" />
        <Mouth pose={pose} x={32} y={41.5} w={6} color="var(--cmp-ink)" />
      </g>
      {pose === 'neutral' && (
        <>
          <Map x={44} y={50} open={false} />
          <circle
            cx={46}
            cy={58}
            r={2.6}
            fill="var(--cmp-honey)"
            stroke="var(--cmp-honey-edge)"
            strokeWidth={1}
          />
        </>
      )}
      {pose === 'pleased' && (
        <>
          <path
            d="M47 52Q54 46 55 36"
            fill="none"
            stroke="var(--cmp-blue)"
            strokeWidth={5}
            strokeLinecap="round"
          />
          <g transform="rotate(12 56 30)">
            <Map x={50} y={24} open={false} />
          </g>
          <circle
            cx={55}
            cy={35}
            r={2.8}
            fill="var(--cmp-honey)"
            stroke="var(--cmp-honey-edge)"
            strokeWidth={1}
          />
        </>
      )}
      {pose === 'encouraging' && (
        <>
          <Map x={21} y={49} open />
          <circle
            cx={21}
            cy={57}
            r={2.6}
            fill="var(--cmp-honey)"
            stroke="var(--cmp-honey-edge)"
            strokeWidth={1}
          />
          <circle
            cx={43}
            cy={57}
            r={2.6}
            fill="var(--cmp-honey)"
            stroke="var(--cmp-honey-edge)"
            strokeWidth={1}
          />
        </>
      )}
    </Frame>
  )
}
