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
        <style>{`
          * { box-sizing: border-box; }
          body { margin: 0; }
          .nav-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
          .nav-scroll::-webkit-scrollbar { display: none; }
          .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
          @media (max-width: 600px) {
            .main-content { padding: 20px 14px !important; }
            .nav-brand { display: none; }
          }
        `}</style>
        <div style={{ minHeight: '100vh', background: '#111', color: '#eee', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
          <nav style={{ borderBottom: '1px solid #1e1e1e', padding: '0 16px', display: 'flex', alignItems: 'center' }}>
            <span className="nav-brand" style={{ fontWeight: 700, marginRight: 16, color: '#3498db', fontSize: 15, whiteSpace: 'nowrap' }}>SureHub</span>
            <div className="nav-scroll" style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
              {TABS.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  background: 'none', border: 'none', color: tab === t.id ? '#fff' : '#555',
                  padding: '15px 14px', cursor: 'pointer', fontSize: 14, whiteSpace: 'nowrap',
                  borderBottom: tab === t.id ? '2px solid #3498db' : '2px solid transparent',
                  transition: 'color 0.15s',
                }}>
                  {t.label}
                </button>
              ))}
            </div>
          </nav>
          <main className="main-content" style={{ maxWidth: 920, margin: '0 auto', padding: '28px 20px' }}>
            {tab === 'resumen' && <ResumenMes />}
            {tab === 'gastos' && <Gastos />}
            {tab === 'categorias' && <Categorias />}
            {tab === 'recurrentes' && <Recurrentes />}
            {tab === 'memoria' && <Memoria />}
          </main>
        </div>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
