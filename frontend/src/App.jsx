import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/Toast'
import ResumenMes from './components/ResumenMes'
import Gastos from './components/Gastos'
import Categorias from './components/Categorias'
import Memoria from './components/Memoria'
import Recurrentes from './components/Recurrentes'

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15000,
      refetchOnWindowFocus: false,
    },
  },
})

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'gastos', label: 'Gastos' },
  { id: 'categorias', label: 'Categorías' },
  { id: 'recurrentes', label: 'Recurrentes' },
  { id: 'memoria', label: 'Memoria' },
]

function App() {
  const [tab, setTab] = useState('resumen')

  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <nav style={{
          borderBottom: '1px solid var(--border)',
          padding: '0 20px',
          display: 'flex',
          alignItems: 'center',
          background: 'var(--surface)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}>
          <span className="nav-brand" style={{
            fontWeight: 700, marginRight: 20, color: 'var(--accent)',
            fontSize: 15, whiteSpace: 'nowrap', letterSpacing: '-0.3px',
          }}>SureHub</span>
          <div className="nav-scroll" style={{ display: 'flex', alignItems: 'center' }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                background: 'none',
                border: 'none',
                color: tab === t.id ? 'var(--text)' : 'var(--text-dim)',
                padding: '16px 14px',
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: tab === t.id ? 600 : 400,
                whiteSpace: 'nowrap',
                borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
                transition: 'color 0.15s',
                transform: 'none',
              }}>
                {t.label}
              </button>
            ))}
          </div>
        </nav>
        <main className="main-content" style={{ maxWidth: 940, margin: '0 auto', padding: '28px 24px' }}>
          {tab === 'resumen' && <ResumenMes />}
          {tab === 'gastos' && <Gastos />}
          {tab === 'categorias' && <Categorias />}
          {tab === 'recurrentes' && <Recurrentes />}
          {tab === 'memoria' && <Memoria />}
        </main>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
