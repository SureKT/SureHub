import { useState, useEffect } from 'react'
import { spotifyStatus, spotifyAnalyze, spotifyAuthUrl } from '../api'
import { useToast } from './Toast'

function StatBox({ label, value }) {
  return (
    <div style={{ flex: 1, minWidth: 90 }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>{value ?? '—'}</div>
    </div>
  )
}

export default function Spotify({ onNavigate }) {
  const toast = useToast()
  const userId = localStorage.getItem('telegram_user_id')

  const [status, setStatus] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState('idle')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!userId) return
    setLoading('status')
    spotifyStatus(userId)
      .then(s => { setStatus(s); setLoading('idle') })
      .catch(() => { setError('Could not reach server'); setLoading('idle') })
  }, [userId])

  const handleAnalyze = async () => {
    setLoading('analyzing')
    setError(null)
    const timeout = setTimeout(() => {
      setLoading('idle')
      setError('Analysis timed out. Try again.')
    }, 45000)
    try {
      const data = await spotifyAnalyze(userId)
      clearTimeout(timeout)
      setAnalysis({
        text: data.analysis,
        stats: data.stats,
        top_genres: data.stats.top_genres,
        timestamp: Date.now(),
      })
      setStatus(s => ({ ...s, spotify_user: data.spotify_user }))
      setLoading('idle')
    } catch (e) {
      clearTimeout(timeout)
      setError('Analysis failed. Try again.')
      setLoading('idle')
    }
  }

  // Not configured
  if (!userId) {
    return (
      <div>
        <div style={{
          background: 'var(--surface2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '14px 18px', marginBottom: 32,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <span style={{ color: 'var(--text-dim)', fontSize: 13 }}>
            Configuration required — connect your Spotify account to use this module.
          </span>
          <button
            onClick={() => onNavigate('settings')}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', padding: 0 }}
          >Go to Settings →</button>
        </div>
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <div style={{ fontSize: 32, marginBottom: 12, color: 'var(--text-muted)', lineHeight: 1 }}>○</div>
          <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500 }}>Not connected</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>Configure your Telegram user ID in Settings to connect your Spotify account.</div>
        </div>
      </div>
    )
  }

  if (error && !status) {
    return (
      <div style={{ color: 'var(--text-dim)', fontSize: 14 }}>
        {error}
        <button
          onClick={() => { setError(null); setLoading('status'); spotifyStatus(userId).then(s => { setStatus(s); setLoading('idle') }).catch(() => { setError('Could not reach server'); setLoading('idle') }) }}
          style={{ marginLeft: 12, background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '4px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}
        >Retry</button>
      </div>
    )
  }

  if (loading === 'status' || !status) {
    return <p style={{ color: 'var(--text-dim)' }}>Loading...</p>
  }

  if (!status.authenticated) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0' }}>
        <div style={{ fontSize: 32, marginBottom: 12, color: 'var(--text-muted)', lineHeight: 1 }}>○</div>
        <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500 }}>Not connected</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4, marginBottom: 24 }}>
          Authorize via Telegram with /spotify_auth, then come back.
        </div>
        <a
          href={spotifyAuthUrl(userId)}
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'inline-block', background: 'var(--accent)', color: 'var(--bg)',
            padding: '9px 20px', borderRadius: 'var(--radius-sm)', fontSize: 13,
            fontWeight: 500, textDecoration: 'none',
          }}
        >Connect Spotify</a>
      </div>
    )
  }

  return (
    <div>
      {/* Hero */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ color: 'var(--text-muted)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 12 }}>Spotify</div>
        <div style={{
          fontSize: 48, fontWeight: 300, letterSpacing: '-1px', lineHeight: 1,
          color: 'var(--text)',
        }}>
          {status.spotify_user || 'Connected'}
        </div>
        {analysis && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
            {analysis.stats.total_liked} liked tracks · {analysis.stats.total_playlists} playlists
            {' · '}Last analyzed {new Date(analysis.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>

      <div style={{ borderBottom: '1px solid var(--border-dim)', marginBottom: 24 }} />

      {/* Analyzing state */}
      {loading === 'analyzing' && (
        <div style={{ color: 'var(--text-dim)', fontSize: 13, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ animation: 'fadeIn 0.5s ease infinite alternate', opacity: 0.6 }}>◌</span>
          Analyzing your library… this may take ~30s
        </div>
      )}

      {/* Actions */}
      {loading !== 'analyzing' && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 32 }}>
          <button
            onClick={handleAnalyze}
            style={{
              background: 'var(--accent)', border: 'none', color: 'var(--bg)',
              padding: '8px 18px', borderRadius: 'var(--radius-sm)', fontSize: 13,
              fontWeight: 500, cursor: 'pointer',
            }}
          >Analyze Library</button>
          <a
            href={spotifyAuthUrl(userId)}
            target="_blank"
            rel="noreferrer"
            style={{
              background: 'none', border: '1px solid var(--border)',
              color: 'var(--text-dim)', padding: '8px 14px', borderRadius: 'var(--radius-sm)',
              fontSize: 13, cursor: 'pointer', textDecoration: 'none', display: 'inline-flex', alignItems: 'center',
            }}
          >Reconnect</a>
        </div>
      )}

      {/* Error inline */}
      {error && (
        <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 20 }}>{error}</div>
      )}

      {/* Analysis block */}
      {analysis && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 12 }}>Analysis</div>
          <div style={{
            background: 'var(--surface2)', border: '1px solid var(--border-dim)',
            borderRadius: 'var(--radius)', padding: '16px 20px',
            fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.7,
            whiteSpace: 'pre-wrap',
          }}>
            {analysis.text}
          </div>
        </div>
      )}

      {/* Stats */}
      {analysis && (
        <div style={{ marginBottom: 32 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>Stats</div>
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <StatBox label="Liked tracks" value={analysis.stats.total_liked} />
            <StatBox label="Playlists" value={analysis.stats.total_playlists} />
            <StatBox label="Avg energy" value={analysis.stats.avg_energy != null ? (analysis.stats.avg_energy * 100).toFixed(0) + '%' : null} />
            <StatBox label="Avg dance" value={analysis.stats.avg_danceability != null ? (analysis.stats.avg_danceability * 100).toFixed(0) + '%' : null} />
          </div>
        </div>
      )}

      {/* Top genres */}
      {analysis && analysis.top_genres?.length > 0 && (
        <div>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 12 }}>Top genres</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {analysis.top_genres.map(([genre], i) => (
              <span key={i} style={{
                background: 'var(--surface3)', color: 'var(--text-dim)',
                padding: '3px 10px', borderRadius: 12, fontSize: 11,
              }}>{genre}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
