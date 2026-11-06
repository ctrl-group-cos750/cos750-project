import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../styles/tokens.css'
import '../styles/global.css'
import '../styles/base.css'
import { UiKitPage } from './UiKitPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <UiKitPage />
  </StrictMode>,
)
