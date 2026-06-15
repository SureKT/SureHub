import { useState, useEffect } from 'react'

const LABEL = { color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 12 }

export default function Settings() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  return (
    <div style={{ maxWidth: 520 }}>

      {/* Appearance */}
      <div>
        <div style={LABEL}>Theme</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[['dark', 'Dark'], ['light', 'Light (pastel)']].map(([val, label]) => (
            <button key={val} onClick={() => setTheme(val)} style={{
              padding: '7px 18px',
              border: theme === val ? '1.5px solid var(--accent)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              background: theme === val ? 'var(--accent-bg)' : 'var(--surface2)',
              color: theme === val ? 'var(--accent)' : 'var(--text-dim)',
              fontSize: 13, cursor: 'pointer', fontWeight: theme === val ? 500 : 400,
            }}>{label}</button>
          ))}
        </div>
      </div>

    </div>
  )
}
