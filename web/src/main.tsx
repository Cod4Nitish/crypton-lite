import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// PWA: installable on phones; pages are never served stale (see frontend/sw.js)
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {})
