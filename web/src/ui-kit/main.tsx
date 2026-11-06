import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import '../styles/tokens.css'
import '../styles/global.css'
import '../styles/base.css'
import { UiKitPage } from './UiKitPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <UiKitPage />
    </BrowserRouter>
  </StrictMode>,
)
