import { useState, useEffect } from 'react'
import { spotifyStatus } from '../api'

const LABEL = { color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 12 }
const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14, width: '100%', maxWidth: 300 }

export default function Settings() {
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')
  const [userId, setUserId] = useState(() => localStorage.getItem('telegram_user_id') || '')
  const [spotifyInfo, setSpotifyInfo] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    if (!userId.trim()) { setSpotifyInfo(null); return }
    spotifyStatus(userId.trim())
      .then(s => setSpotifyInfo(s))
      .catch(() => setSpotifyInfo(null))
  }, [userId])

  const handleUserIdBlur = () => localStorage.setItem('telegram_user_id', userId.trim())

  return (
    <div style={{ maxWidth: 520 }}>

      {/* Appearance */}
      <div style={{ marginBottom: 40 }}>
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

      {/* Spotify */}
      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: 32 }}>
        <div style={LABEL}>Telegram User ID</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
          Needed to link your Spotify OAuth token. Find it with @userinfobot on Telegram.
        </div>
        <input type="text" value={userId} onChange={e => setUserId(e.target.value)} onBlur={handleUserIdBlur}
          placeholder="e.g. 123456789" style={inputStyle} />
        <div style={{ marginTop: 8, fontSize: 12 }}>
          {spotifyInfo?.authenticated
            ? <span style={{ color: 'var(--green)' }}>✓ Spotify connected as {spotifyInfo.spotify_user}</span>
            : userId ? <span style={{ color: 'var(--text-muted)' }}>○ Not connected</span>
            : null}
        </div>
      </div>

    </div>
  )
}
