import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/Toast'
import Sidebar from './components/Sidebar'
import ResumenMes from './components/ResumenMes'
import Gastos from './components/Gastos'
import Categorias from './components/Categorias'
import Memoria from './components/Memoria'
import Recurrentes from './components/Recurrentes'
import Spotify from './components/Spotify'
import Settings from './components/Settings'
import Diary from './components/Diary'
import Timeline from './components/Timeline'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15000,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  const [view, setView] = useState('summary')

  useEffect(() => {
    const theme = localStorage.getItem('theme') || 'dark'
    document.documentElement.setAttribute('data-theme', theme)
  }, [])
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('sidebar-collapsed') === 'true'
  )

  const toggleCollapse = () => {
    setCollapsed(c => {
      const next = !c
      localStorage.setItem('sidebar-collapsed', String(next))
      return next
    })
  }

  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
          <Sidebar
            activeView={view}
            onNavigate={setView}
            collapsed={collapsed}
            onToggleCollapse={toggleCollapse}
          />
          <main style={{ flex: 1, padding: '32px 48px', overflowY: 'auto', minWidth: 0 }}>
            {view === 'summary' && <ResumenMes />}
            {view === 'expenses' && <Gastos />}
            {view === 'categories' && <Categorias />}
            {view === 'recurring' && <Recurrentes />}
            {view === 'memory' && <Memoria />}
            {view === 'spotify' && <Spotify onNavigate={setView} />}
            {view === 'settings' && <Settings />}
            {view === 'diary' && <Diary />}
            {view === 'timeline' && <Timeline />}
          </main>
        </div>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
