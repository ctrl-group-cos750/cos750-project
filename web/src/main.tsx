import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { retryUnlessRefused } from './api/retry.ts'
import './styles/tokens.css'
import './styles/global.css'
import './styles/base.css'
import App from './App.tsx'
import { applyTheme, initialTheme } from './theme/theme.ts'

applyTheme({ theme: initialTheme() })

// Every query: a 4xx (403 locked, 404 missing) isn't asked again, so a page says why at once
// instead of spinning for 7-10 s through React Query's three retries (#146).
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: retryUnlessRefused } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
