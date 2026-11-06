import { useQuery } from '@tanstack/react-query'
import { LoaderCircle } from 'lucide-react'
import { useParams } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { BfsVisualizer } from './BfsVisualizer.tsx'
import { fetchBfsScenario } from './bfs.api.ts'

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
        <LoadCircle className="size-5 animate-spin" aria-hidden="true" />
        Loading graph...
      </div>
    )
  }

  if (query.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Could not load the graph</AlertTitle>
        <AlertDescription>{query.error.message}</AlertDescription>
      </Alert>
    )
  }

  return <BfsVisualizer scenario={query.data} />
}
