type State = 'unvisited' | 'queued' | 'current' | 'visited'

const symbols: Record<State, string> = { unvisited: '', queued: '…', current: '▶', visited: '✓' }

const vertices: { id: string; x: number; y: number; state: State }[] = [
  { id: 'A', x: 60, y: 60, state: 'visited' },
  { id: 'B', x: 180, y: 30, state: 'current' },
  { id: 'C', x: 180, y: 120, state: 'queued' },
  { id: 'D', x: 300, y: 30, state: 'queued' },
  { id: 'E', x: 300, y: 120, state: 'unvisited' },
]

const edges: [string, string, boolean][] = [
  ['A', 'B', true],
  ['A', 'C', true],
  ['B', 'D', true],
  ['C', 'E', false],
  ['D', 'E', false],
]

const at = (id: string) => vertices.find((v) => v.id === id)!

/** A static example of the four vertex states, for whoever builds GraphCanvas. */
export function BfsStatesSample() {
  return (
    <div>
      <svg
        viewBox="0 0 360 160"
        width="100%"
        style={{ maxWidth: 480 }}
        // An inline SVG drawing needs role="img" to be read as one image with a name.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        role="img"
        aria-label="Sample graph: A visited, B current, C and D queued, E unvisited"
      >
        {edges.map(([from, to, traversed]) => (
          <line
            key={from + to}
            x1={at(from).x}
            y1={at(from).y}
            x2={at(to).x}
            y2={at(to).y}
            stroke={traversed ? 'var(--bfs-edge-traversed)' : 'var(--bfs-edge)'}
            strokeWidth={traversed ? 3 : 2}
          />
        ))}
        {vertices.map(({ id, x, y, state }) => (
          <g key={id}>
            <circle
              cx={x}
              cy={y}
              r={20}
              fill={`var(--bfs-${state}-fill)`}
              stroke={`var(--bfs-${state}-stroke)`}
              strokeWidth={state === 'current' ? 4 : 2}
            />
            <text
              x={x}
              y={y + 6}
              textAnchor="middle"
              fontFamily="var(--font-mono)"
              fontWeight={600}
              fontSize={18}
              fill={state === 'current' ? 'var(--bfs-current-text)' : 'var(--color-text)'}
            >
              {id}
            </text>
            {symbols[state] && (
              <text x={x + 18} y={y - 16} fontSize={14} fill="var(--color-text)">
                {symbols[state]}
              </text>
            )}
          </g>
        ))}
      </svg>
      <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.25rem 1rem' }}>
        <dt>▶ Current</dt>
        <dd style={{ margin: 0 }}>The vertex being processed: its neighbours are queued next.</dd>
        <dt>… Queued</dt>
        <dd style={{ margin: 0 }}>Discovered and waiting in the queue.</dd>
        <dt>✓ Visited</dt>
        <dd style={{ margin: 0 }}>Already processed and in the traversal order.</dd>
        <dt>Unvisited</dt>
        <dd style={{ margin: 0 }}>Not discovered yet.</dd>
      </dl>
    </div>
  )
}
