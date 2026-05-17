import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResumenMes from './components/ResumenMes'
import Gastos from './components/Gastos'
import Categorias from './components/Categorias'

const qc = new QueryClient()

const TABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'gastos', label: 'Gastos' },
  { id: 'categorias', label: 'Categorías' },
]

function App() {
  const [tab, setTab] = useState('resumen')

  return (
    <QueryClientProvider client={qc}>
      <div style={{ minHeight: '100vh', background: '#111', color: '#eee', fontFamily: 'system-ui, sans-serif' }}>
        <nav style={{ borderBottom: '1px solid #222', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontWeight: 700, marginRight: 20, color: '#3498db' }}>SureHub</span>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: 'none', border: 'none', color: tab === t.id ? '#fff' : '#666',
              padding: '16px 12px', cursor: 'pointer', fontSize: 14,
              borderBottom: tab === t.id ? '2px solid #3498db' : '2px solid transparent',
            }}>
              {t.label}
            </button>
          ))}
        </nav>
        <main style={{ maxWidth: 800, margin: '0 auto', padding: '32px 24px' }}>
          {tab === 'resumen' && <ResumenMes />}
          {tab === 'gastos' && <Gastos />}
          {tab === 'categorias' && <Categorias />}
        </main>
      </div>
    </QueryClientProvider>
  )
}

export default App
