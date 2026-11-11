import { useId } from 'react'
import type { Drawing, DrawnEdge } from './drawing.ts'
import { layOut, RADIUS } from './layout.ts'

const STROKE: Record<DrawnEdge['mark'], string> = {
  plain: 'var(--bfs-unvisited-stroke)',
  wrong: 'var(--destructive)',
  missed: 'var(--success)',
}

type GraphDrawingProps = {
  drawing: Drawing
  /** Larger label text, for phones and the full-size view. */
  large?: boolean
}

/** A graph drawn from data in the app's graph and theme tokens, so it follows light and dark
 * mode like the BFS visualiser. Its text alternative is the drawing's description. */
export function GraphDrawing({ drawing, large = false }: GraphDrawingProps) {
  const id = useId()
  const { situation } = drawing
  const { laid, names: markBoxes } = layOut(drawing, large)
  const nameSize = large ? 22 : 15
  const labelSize = large ? 20 : 14
  const halo = {
    stroke: 'var(--color-surface-sunken)',
    strokeWidth: 5,
    strokeLinejoin: 'round' as const,
    paintOrder: 'stroke' as const,
  }
  const marks = new Map(drawing.vertices.map((vertex) => [vertex.id, vertex]))

  return (
    // An inline SVG, not an <img>: its colours come from the theme's CSS custom properties.
    <svg
      viewBox={`0 0 ${situation.width} ${situation.height}`}
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role -- an inline SVG, so it can use the theme's tokens
      role="img"
      aria-labelledby={`${id}-title ${id}-desc`}
      className="block h-auto w-full"
      data-testid="graph-drawing"
    >
      <title id={`${id}-title`}>{drawing.title}</title>
      <desc id={`${id}-desc`}>{drawing.description}</desc>
      <defs>
        {(['plain', 'wrong', 'missed'] as const).map((mark) => (
          <marker
            key={mark}
            id={`${id}-arrow-${mark}`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerUnits="userSpaceOnUse"
            markerWidth="18"
            markerHeight="18"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" fill={STROKE[mark]} />
          </marker>
        ))}
      </defs>
      <rect
        x="2"
        y="2"
        width={situation.width - 4}
        height={situation.height - 4}
        rx="16"
        fill="var(--color-surface-sunken)"
        stroke="var(--color-line)"
        strokeWidth="2"
      />
      {laid.map(({ edge, d }) => (
        <path
          key={`${edge.from}-${edge.to}`}
          d={d}
          fill="none"
          stroke={STROKE[edge.mark]}
          strokeWidth={edge.mark === 'plain' ? 4 : 5}
          strokeDasharray={edge.mark === 'wrong' ? '12 9' : undefined}
          strokeLinecap="round"
          markerEnd={edge.directed ? `url(#${id}-arrow-${edge.mark})` : undefined}
          data-edge={`${edge.from}${edge.to}`}
          data-mark={edge.mark}
        />
      ))}
      {situation.places.map((place) => {
        const mark = marks.get(place.id)
        return (
          <g key={place.id} data-vertex={place.id} data-mark={mark?.mark}>
            <circle
              cx={place.x}
              cy={place.y}
              r={RADIUS}
              fill="var(--bfs-unvisited-fill)"
              stroke={mark ? STROKE[mark.mark ?? 'plain'] : 'var(--bfs-unvisited-stroke)'}
              strokeWidth="4"
              strokeDasharray={mark?.mark === 'wrong' ? '8 6' : undefined}
            />
            <text
              x={place.x}
              y={place.y + 9}
              fontSize="26"
              fontWeight="700"
              textAnchor="middle"
              fill="var(--color-text)"
            >
              {place.id}
            </text>
            {place.name && (
              <text
                x={place.x}
                y={place.y + RADIUS + nameSize + 2}
                fontSize={nameSize}
                fontWeight="500"
                textAnchor="middle"
                fill="var(--color-text-muted)"
                {...halo}
              >
                {place.name}
              </text>
            )}
          </g>
        )
      })}
      {drawing.vertices.map((vertex, index) =>
        vertex.label && markBoxes[index] ? (
          <text
            key={`mark-${vertex.id}`}
            x={markBoxes[index].x + markBoxes[index].w / 2}
            y={markBoxes[index].y + markBoxes[index].h - 5}
            fontSize={labelSize}
            fontWeight="700"
            textAnchor="middle"
            fill={STROKE[vertex.mark ?? 'plain']}
            {...halo}
          >
            {vertex.label}
          </text>
        ) : null,
      )}
      {laid.map(({ edge, label }) =>
        label && edge.label ? (
          <text
            key={`label-${edge.from}-${edge.to}`}
            x={label.x}
            y={label.y}
            fontSize={labelSize}
            fontWeight="700"
            textAnchor="middle"
            fill={STROKE[edge.mark]}
            {...halo}
          >
            {edge.label}
          </text>
        ) : null,
      )}
    </svg>
  )
}
