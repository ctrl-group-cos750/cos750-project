import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { retryUnlessRefused } from './api/retry.ts'
import './styles/tokens.css'
import './styles/global.css'
import './styles/base.css'
import './styles/backgrounds.css'
import App from './App.tsx'
import { storedBackground } from './features/progress/preferences.ts'
import { applyBackground } from './theme/background.ts'
import { applyTheme, initialTheme } from './theme/theme.ts'

applyTheme({ theme: initialTheme() })
// The default page background until a student signs in (then theirs: SignedInLayout).
applyBackground({ background: storedBackground() })

// Every query: a 4xx (403 locked, 404 missing) isn't asked again, so a page says why at once
// instead of spinning for 7-10 s through React Query's three retries (#146).
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: retryUnlessRefused } } })

// A data router, so an editor can ask before a link discards unsaved changes (useBlocker). The
// routes themselves stay in App's <Routes>, under one splat route.
const router = createBrowserRouter([{ path: '*', element: <App /> }])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
