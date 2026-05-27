# Spotify Frontend — Design Spec
Date: 2026-05-27

## Overview

React view for the Spotify module. Backend already complete (`/api/spotify`). This spec covers only the frontend: component structure, state machine, API calls, and integration into the existing app shell.

---

## Backend contract (existing)

| Endpoint | Method | Description |
|---|---|---|
| `/api/spotify/status?telegram_user_id=<id>` | GET | Returns `{ connected: bool, display_name: str \| null }` |
| `/api/spotify/analyze` | POST | Body `{ telegram_user_id }`. Long-running (~30s). Returns `{ analysis: str, stats: { liked_tracks, playlists, avg_energy, avg_danceability }, top_genres: str[] }` |
| `/api/spotify/auth/start?telegram_user_id=<id>` | GET | Redirects to Spotify OAuth |

`telegram_user_id` is stored in `localStorage` under key `telegram_user_id`. Set from the Settings view.

---

## Views / states

The `Spotify` component renders one of three states based on runtime data — no tab switcher in production, state is derived:

### A — Not configured
Triggered when `localStorage.telegram_user_id` is empty/missing.

- Banner: "Configuración necesaria — conecta tu cuenta de Spotify para usar este módulo." + link "Ir a Settings →" (navigates to Settings view in the app)
- Empty state below: icon + "Not connected" + "Configure your Telegram user ID in Settings to connect your Spotify account."

### B — Analyzing
Triggered when a POST to `/analyze` is in-flight.

- Hero: display name (from status), liked tracks + playlists counts
- Spinner row: "Analyzing your library… this may take ~30s"
- No action buttons while loading

### C — Connected (default when configured + no active analysis)
Triggered when status returns `connected: true` and no analysis is in-flight.

- **Hero**: display name at `text-5xl font-light` — the focal element of the view
- Metadata row: `{liked_tracks} liked tracks · {playlists} playlists · Last analyzed {time ago}` (time ago only if analysis result exists)
- Divider
- Action buttons: **Analyze Library** (accent, triggers POST /analyze) + **Disconnect** (ghost)
- **ANALYSIS block** (shown only if a result exists): label `ANALYSIS` + card with Claude's text. Persisted in component state for the session; re-fetched on new analysis.
- **STATS row**: 4 columns — liked tracks / playlists / avg energy / avg danceability. Labels `text-xs uppercase tracking-wide text-faint`.
- **TOP GENRES**: label + flat row of grey badges (`bg-subtle text-muted`).

### D — Connected, no analysis yet
Same as C but ANALYSIS block hidden, stats show live data from status (only liked_tracks and playlists available without analysis).

---

## Settings view

Global sidebar entry "Settings" — single page with sections.

### Appearance section
- Label: `THEME`
- Two buttons: **Dark** / **Light (pastel)** — active state uses `--accent` outline/fill
- Persisted in `localStorage` under key `theme` (`dark` | `light`)
- Applies `data-theme="light"` on `<html>` element when active; default is dark

### Spotify section
- Label: `TELEGRAM USER ID`
- Helper: "Needed to link your Spotify OAuth token. Find it with @userinfobot on Telegram."
- Input field — on blur/change saves to `localStorage`
- Status indicator below input: `✓ Spotify connected as {display_name}` (green, `text-xs`) — fetched live from `/api/spotify/status` when a user ID is present. Or `○ Not connected` (muted) if status returns `connected: false`.

---

## Component structure

```
frontend/src/
  components/
    Spotify.jsx          # main view, owns status + analysis state
    Settings.jsx         # new global settings view
  api.js                 # add spotifyStatus(), spotifyAnalyze()
  App.jsx                # add <Settings /> route, pass setView to Sidebar
  Sidebar.jsx            # add Spotify > Library entry + Settings entry at bottom
```

`Spotify.jsx` internal state:
```js
{
  status: null | { connected, display_name, liked_tracks, playlists },
  analysis: null | { text, stats, top_genres, timestamp },
  loading: 'idle' | 'status' | 'analyzing',
  error: null | string
}
```

On mount: read `telegram_user_id` from localStorage → if present, call `spotifyStatus()` → set state.

`Settings.jsx` internal state: reads/writes localStorage only. No API calls except the Spotify status check (to show connected indicator).

---

## Theme system

CSS custom properties on `:root` (dark, default) and `[data-theme="light"]` override block.

Dark palette (existing):
- `--bg: #0e0e0e`, `--surface: #1a1a1a`, `--surface2: #222`, `--surface3: #2a2a2a`
- `--accent: #c8f0dc`, `--accent-fg: #0e0e0e`
- `--text-primary: #e8e8e8`, `--text-muted: #888`, `--text-faint: #555`

Light (pastel) palette:
- `--bg: #f5f0e8`, `--surface: #ede8df`, `--surface2: #e5e0d7`, `--surface3: #ddd8cf`
- `--accent: #4a9e72`, `--accent-fg: #fff`
- `--text-primary: #1a1a1a`, `--text-muted: #666`, `--text-faint: #999`

Toggle: `document.documentElement.setAttribute('data-theme', theme)` + persist to localStorage.

Theme CSS lives in `index.css` (global). Sidebar, App, all existing components inherit via CSS vars — no per-component changes needed.

---

## Navigation

Current app uses a `view` state in `App.jsx` (`'summary' | 'expenses' | ...`). Extend with `'spotify'` and `'settings'`.

`Sidebar.jsx` additions:
- Under `SPOTIFY` section: **Library** item → sets view to `'spotify'`
- Bottom of sidebar (below Memory): **Settings** item → sets view to `'settings'`

---

## Error handling

- Status fetch fails → show "Could not reach server" banner, retry button
- Analyze fetch fails / times out (>45s) → show error inline in the analysis block area: "Analysis failed. Try again."
- No special offline handling needed (personal local app)

---

## Out of scope

- Spotify OAuth flow in the browser (handled via Telegram bot)
- Playlist browsing / track lists
- Historical analysis comparison
- Pagination of genres/stats
