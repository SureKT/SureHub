# SureHub Shell Redesign

**Date:** 2026-05-18  
**Status:** Approved  
**Scope:** App shell (navigation + layout) + identity + content view polish

---

## Problem

Current UI reads as generic AI-generated CRUD web app. Specific issues:
- Horizontal tab nav feels like a website, not a product
- No identity — no logo mark, no personality, no iconography
- Data presented flatly, nothing draws attention
- No sense of "ecosystem of apps" — just tabs

**References:** Linear, Vercel dashboard

---

## Solution: Dark OS Shell (Approach A)

Replace horizontal tabs with a collapsible sidebar. Establish identity through logo mark, iconography, and consistent accent usage. Polish data presentation without full refactor.

---

## 1. Shell Layout

```
┌───────────────┬──────────────────────────────────────┐
│   Sidebar     │         Content area                 │
│   220px       │         calc(100vw - 220px)           │
│  (48px coll.) │         padding: 0 48px               │
└───────────────┴──────────────────────────────────────┘
```

- Sidebar: fixed left, full height, `background: var(--surface)`, `border-right: 1px solid var(--border-dim)`
- Content: `padding: 32px 48px`, no hard `max-width` — relies on padding for breathing room
- Collapse toggle: bottom-left button `⟨` / `⟩`, persisted to `localStorage`
- Collapsed state: 48px wide, icons only, tooltips on hover

---

## 2. Sidebar Anatomy

```
┌──────────────┐
│ ◈  SureHub   │  logo mark (SVG) + wordmark, --accent color
├──────────────┤
│              │
│ ⬡ FINANZAS   │  section label: text-xs uppercase tracking-wide
│   Resumen    │  active item: accent left-border 2px + surface2 bg
│   Gastos     │  inactive: text-dim, hover: surface3 bg
│   Categorías │
│   Recurrentes│
│   Memoria    │
│              │
│ ⬡ AUTOMATI.  │  future modules: opacity 0.35, cursor default
│ ⬡ HERRAMIENT │
│              │
├──────────────┤
│ ⟨            │  collapse toggle
└──────────────┘
```

**Active item styles:**
- `border-left: 2px solid var(--accent)`
- `background: var(--surface2)`
- `color: var(--text)`

**Inactive item styles:**
- `color: var(--text-dim)`
- hover: `background: var(--surface3)`

**Collapsed state:**
- Section icons only, centered
- Item labels hidden
- `title` attribute for tooltip on hover

**Future modules** (Automatizaciones, Herramientas):
- Visible in sidebar with icon + label
- `opacity: 0.35`, `pointer-events: none`
- Communicates "product in progress", not emptiness

---

## 3. Identity

### Logo Mark
- Simple SVG geometric mark (◈ style), `color: var(--accent)`
- Inline SVG component, no external file dependency
- Sidebar header: `[mark] SureHub` — 15px, fontWeight 700, letterSpacing -0.3px
- Collapsed: mark only, centered

### Iconography
- Library: **Lucide React** (tree-shakeable, ~2KB per icon, Vite compatible)
- Module icons: `BarChart2` (Finanzas), `Zap` (Automatizaciones), `Wrench` (Herramientas)
- Size: 14px in sidebar, stroke 1.5

### Accent Usage
- Logo mark
- Active nav item left border
- One key data point per view (hero number, primary action button)
- No more than one element per visible area

### Typography
- Font: DM Sans (already loaded) — no change
- Data/numbers: `font-variant-numeric: tabular-nums`, `font-weight: 300` for hero values
- Section labels: `letter-spacing: 2px` in sidebar (up from 1.2px)
- Body content: 13-14px regular

---

## 4. Content View Polish

### Global
- Remove `maxWidth: 940px` from `<main>` — use `padding: 32px 48px` instead
- Content breathes on larger screens

### Resumen
- No structural changes — hero already implemented
- Charts: use palette variables (`--accent`, `--text-dim`) instead of Recharts defaults

### Gastos
- Date format: `dd MMM` (e.g. "15 may") instead of `dd/mm/yyyy`
- Amount: no color change — keep neutral (semantic color reserved for alerts only)

### Categorías / Recurrentes
- Budget progress bar: 3px → 4px height
- No other changes — flat rows already implemented

### Memoria
- No changes needed

---

## 5. Component Breakdown

New/modified components:

| Component | Action | Notes |
|-----------|--------|-------|
| `App.jsx` | Modify | Replace tab nav with sidebar layout |
| `Sidebar.jsx` | New | Collapsible sidebar with nav items |
| `LogoMark.jsx` | New | Inline SVG mark |
| `Gastos.jsx` | Minor | Date format change |
| `ResumenMes.jsx` | Minor | Chart color tokens |
| `Categorias.jsx` | Minor | Progress bar height |
| `Recurrentes.jsx` | Minor | Progress bar height |
| `index.css` | Minor | Remove main max-width if set there |

---

## 6. Out of Scope

- Mobile layout (Telegram handles mobile)
- New modules (Automatizaciones, Herramientas) — sidebar slots only
- Animation/transition system beyond existing `transition: color 0.15s`
- Dark/light mode toggle

---

## 7. Success Criteria

- Sidebar renders, collapses, persists state
- All 5 Finanzas views accessible via sidebar
- Logo mark visible, recognizable, in accent color
- Future module slots visible but disabled
- No regression in existing functionality
- Feels like Linear, not a generic web form
