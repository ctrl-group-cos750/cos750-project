import { useQuery } from '@tanstack/react-query'
import { LoaderCircle } from 'lucide-react'
import { useParams } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { BackLink } from '../../components/BackLink.tsx'
import type { BackState } from '../../components/backState.ts'
import { BfsVisualizer } from './BfsVisualizer.tsx'
import { fetchBfsScenario } from './bfs.api.ts'

/** Opened from an address rather than module 3's link: back to the map, never a dead end (#146). */
const TO_THE_MAP: BackState = { backTo: '/', backLabel: 'Back to your modules' }

export function BfsPage() {
  const scenarioId = Number(useParams().scenarioId)
  const validScenarioId = Number.isInteger(scenarioId) && scenarioId > 0

  const query = useQuery({
    queryKey: ['graphs', scenarioId, 'bfs'],
    queryFn: () => fetchBfsScenario({ scenarioId }),
    enabled: validScenarioId,
  })

  if (!validScenarioId) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Invalid graph</AlertTitle>
        <AlertDescription>The graph identifier must be a positive number.</AlertDescription>
      </Alert>
    )
  }

  if (query.isPending) {
    return (
      <div className="flex min-h-48 items-center justify-center gap-2 text-muted-foreground">
        <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
        Loading graph...
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="grid justify-items-start gap-3">
        <Alert variant="destructive">
          <AlertTitle>Could not load the graph</AlertTitle>
          <AlertDescription>{query.error.message}</AlertDescription>
        </Alert>
        <BackLink fallback={TO_THE_MAP} />
      </div>
    )
  }

  return (
    <>
      <BackLink fallback={TO_THE_MAP} />
      <BfsVisualizer key={query.data.id} scenario={query.data} />
    </>
  )
}
