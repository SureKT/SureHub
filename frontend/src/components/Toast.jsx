import { useState, useEffect, createContext, useContext, useCallback } from 'react'

const ToastCtx = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const add = useCallback((msg, type = 'ok') => {
    const id = Date.now()
    setToasts(t => [...t, { id, msg, type }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3000)
  }, [])

  return (
    <ToastCtx.Provider value={add}>
      {children}
      <div style={{ position: 'fixed', bottom: 24, right: 24, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 1000 }}>
        {toasts.map(t => (
          <div key={t.id} style={{
            background: t.type === 'error' ? '#c0392b' : '#27ae60',
            color: '#fff', padding: '10px 16px', borderRadius: 8,
            fontSize: 14, boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            animation: 'fadeIn 0.2s ease'
          }}>
            {t.msg}
          </div>
        ))}
      </div>
      <style>{`@keyframes fadeIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: none } }`}</style>
    </ToastCtx.Provider>
  )
}

export const useToast = () => useContext(ToastCtx)
