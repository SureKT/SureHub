# Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace horizontal tab navigation with a collapsible sidebar, add logo mark + Lucide icons for identity, and polish data presentation across views.

**Architecture:** New `Sidebar.jsx` component handles all navigation state. `App.jsx` switches from tab layout to flex row (sidebar + main). `LogoMark.jsx` is a standalone inline SVG. Content views receive minor polishes only.

**Tech Stack:** React + Vite, lucide-react (new), CSS custom properties, localStorage for collapse persistence.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/components/LogoMark.jsx` | Create | Inline SVG geometric mark |
| `frontend/src/components/Sidebar.jsx` | Create | Collapsible sidebar with nav + module slots |
| `frontend/src/App.jsx` | Modify | Swap tab nav for sidebar layout |
| `frontend/src/index.css` | Modify | Remove obsolete nav utilities, body layout |
| `frontend/src/components/Gastos.jsx` | Modify | Date format `dd MMM` |
| `frontend/src/components/ResumenMes.jsx` | Modify | Pie chart color palette |
| `frontend/src/components/Categorias.jsx` | Modify | Progress bar 3px → 4px |
| `frontend/src/components/Recurrentes.jsx` | Modify | Progress bar 3px → 4px |

---

## Task 1: Install lucide-react

**Files:**
- Modify: `frontend/package.json` (via npm)

- [ ] **Step 1: Install**

```bash
cd frontend && npm install lucide-react
```

Expected output: `added N packages` with lucide-react in dependencies.

- [ ] **Step 2: Verify import works**

```bash
node -e "require('./node_modules/lucide-react')" 2>&1 | head -3
```

Expected: no error (or just a warning about ESM — that's fine, Vite handles it).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: install lucide-react"
```

---

## Task 2: Create LogoMark.jsx

**Files:**
- Create: `frontend/src/components/LogoMark.jsx`

- [ ] **Step 1: Create component**

```jsx
export default function LogoMark({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="2.5" y="2.5" width="11" height="11" rx="1"
        stroke="var(--accent)" strokeWidth="1.5"
        transform="rotate(45 8 8)" />
      <rect x="5.5" y="5.5" width="5" height="5" rx="0.5"
        fill="var(--accent)"
        transform="rotate(45 8 8)" />
    </svg>
  )
}
```

- [ ] **Step 2: Smoke test in browser**

Temporarily import and render `<LogoMark />` anywhere visible (e.g. top of App.jsx), start dev server (`cd frontend && npm run dev`), confirm diamond mark renders in accent color. Remove temp import after confirming.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LogoMark.jsx
git commit -m "feat: add LogoMark inline SVG component"
```

---

## Task 3: Create Sidebar.jsx

**Files:**
- Create: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1: Create component**

```jsx
import { BarChart2, Zap, Wrench } from 'lucide-react'
import LogoMark from './LogoMark'

const MODULES = [
  {
    id: 'finanzas',
    label: 'Finanzas',
    icon: BarChart2,
    active: true,
    items: [
      { id: 'resumen', label: 'Resumen' },
      { id: 'gastos', label: 'Gastos' },
      { id: 'categorias', label: 'Categorías' },
      { id: 'recurrentes', label: 'Recurrentes' },
      { id: 'memoria', label: 'Memoria' },
    ],
  },
  {
    id: 'automatizaciones',
    label: 'Automatizaciones',
    icon: Zap,
    active: false,
    items: [],
  },
  {
    id: 'herramientas',
    label: 'Herramientas',
    icon: Wrench,
    active: false,
    items: [],
  },
]

export default function Sidebar({ activeView, onNavigate, collapsed, onToggleCollapse }) {
  return (
    <aside style={{
      width: collapsed ? 48 : 220,
      minWidth: collapsed ? 48 : 220,
      height: '100vh',
      position: 'sticky',
      top: 0,
      background: 'var(--surface)',
      borderRight: '1px solid var(--border-dim)',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.2s, min-width 0.2s',
      overflow: 'hidden',
    }}>

      {/* Header */}
      <div style={{
        padding: collapsed ? '0' : '0 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        justifyContent: 'center',
        borderBottom: '1px solid var(--border-dim)',
        height: 56,
        flexShrink: 0,
      }}>
        <LogoMark size={16} />
        {!collapsed && (
          <span style={{
            color: 'var(--accent)',
            fontSize: 15,
            fontWeight: 700,
            letterSpacing: '-0.3px',
            whiteSpace: 'nowrap',
          }}>SureHub</span>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 0' }}>
        {MODULES.map(module => (
          <div
            key={module.id}
            style={{
              marginBottom: 8,
              opacity: module.active ? 1 : 0.35,
              pointerEvents: module.active ? 'auto' : 'none',
            }}
          >
            {/* Section label */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: collapsed ? '6px 0' : '4px 16px',
                justifyContent: collapsed ? 'center' : 'flex-start',
              }}
              title={collapsed ? module.label : undefined}
            >
              <module.icon size={14} strokeWidth={1.5} color="var(--text-muted)" />
              {!collapsed && (
                <span style={{
                  color: 'var(--text-muted)',
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '2px',
                  fontWeight: 500,
                }}>
                  {module.label}
                </span>
              )}
            </div>

            {/* Items — hidden when collapsed */}
            {!collapsed && module.items.map(item => {
              const isActive = activeView === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    background: isActive ? 'var(--surface2)' : 'none',
                    border: 'none',
                    borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                    borderRadius: 0,
                    color: isActive ? 'var(--text)' : 'var(--text-dim)',
                    padding: '7px 16px',
                    fontSize: 13,
                    cursor: 'pointer',
                    fontWeight: isActive ? 500 : 400,
                    whiteSpace: 'nowrap',
                    transition: 'background 0.15s, color 0.15s',
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'var(--surface3)' }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'none' }}
                >
                  {item.label}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div style={{
        padding: '12px',
        borderTop: '1px solid var(--border-dim)',
        display: 'flex',
        justifyContent: collapsed ? 'center' : 'flex-start',
        flexShrink: 0,
      }}>
        <button
          onClick={onToggleCollapse}
          title={collapsed ? 'Expandir sidebar' : 'Colapsar sidebar'}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px 8px',
            fontSize: 14,
            borderRadius: 'var(--radius-sm)',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--text-dim)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
        >
          {collapsed ? '⟩' : '⟨'}
        </button>
      </div>
    </aside>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Sidebar.jsx
git commit -m "feat: add collapsible Sidebar component with module nav"
```

---

## Task 4: Update App.jsx

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Replace App.jsx**

```jsx
import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ToastProvider } from './components/Toast'
import Sidebar from './components/Sidebar'
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

function App() {
  const [view, setView] = useState('resumen')
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
            {view === 'resumen' && <ResumenMes />}
            {view === 'gastos' && <Gastos />}
            {view === 'categorias' && <Categorias />}
            {view === 'recurrentes' && <Recurrentes />}
            {view === 'memoria' && <Memoria />}
          </main>
        </div>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
```

- [ ] **Step 2: Verify in browser**

Run `cd frontend && npm run dev`. Confirm:
- Sidebar renders left, content right
- All 5 views navigate correctly
- Collapse toggle works and persists on refresh
- Future modules (Automatizaciones, Herramientas) show at 35% opacity, unclickable

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: replace tab nav with sidebar layout"
```

---

## Task 5: Update index.css

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Remove obsolete nav utilities, add layout reset**

Remove the `.nav-scroll`, `.nav-brand` utility classes (no longer used). Update the media query block. Add `html, body` height constraint so the flex layout fills viewport correctly.

Replace the bottom section of `index.css` (from `/* ── Utilities ──*/` to end of file) with:

```css
/* ── Utilities ── */
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* Layout */
html, body, #root { height: 100%; }

@keyframes slideUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
@keyframes fadeIn  { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
```

- [ ] **Step 2: Verify**

Confirm no visual regressions — sidebar full height, content scrolls independently.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "refactor: remove obsolete nav CSS, add layout height reset"
```

---

## Task 6: Polish — Gastos date format

**Files:**
- Modify: `frontend/src/components/Gastos.jsx`

- [ ] **Step 1: Add formatDate helper and apply**

After the `const td = ...` line at the bottom of the file, the date is formatted inline in the table row at this line:
```jsx
<td style={{ ...td, color: 'var(--text-dim)', fontSize: 13 }}>{new Date(g.fecha).toLocaleDateString('es-ES')}</td>
```

Add a helper function near the top of the file (after imports, before `FUENTE_STYLE`):
```js
const formatDate = (dateStr) =>
  new Date(dateStr).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })
```

Replace the inline date formatting:
```jsx
<td style={{ ...td, color: 'var(--text-dim)', fontSize: 13 }}>{formatDate(g.fecha)}</td>
```

Also apply to the edit row where it shows date (the `EditRow` component uses an `<input type="date">` — no change needed there, that's the edit form not display).

- [ ] **Step 2: Verify**

In browser, navigate to Gastos. Dates should show as "15 may", "03 ene", etc. instead of "15/05/2026".

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Gastos.jsx
git commit -m "refactor: Gastos date format dd MMM"
```

---

## Task 7: Polish — ResumenMes pie chart colors

**Files:**
- Modify: `frontend/src/components/ResumenMes.jsx`

- [ ] **Step 1: Replace COLORS array**

At the top of `ResumenMes.jsx`, replace:
```js
const COLORS = ['#3498db','#2ecc71','#e74c3c','#f39c12','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']
```

With palette-derived colors:
```js
const COLORS = [
  '#c8f0dc', // accent mint
  '#a78bfa', // purple
  '#fbbf24', // orange
  '#f87171', // red
  '#4ade80', // green
  '#9b9b97', // grey
  '#7dd3fc', // sky
  '#f9a8d4', // pink
  '#86efac', // light green
  '#c4b5fd', // light purple
  '#fca5a5', // light red
  '#fde68a', // light yellow
]
```

- [ ] **Step 2: Verify**

Navigate to Resumen and select a past month that has data (e.g. from the month selector). Pie chart should render with the new palette — cohesive tones rather than random saturated colors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ResumenMes.jsx
git commit -m "refactor: ResumenMes pie chart palette from design tokens"
```

---

## Task 8: Polish — Progress bar height

**Files:**
- Modify: `frontend/src/components/ResumenMes.jsx` (BarraProgreso)
- Modify: `frontend/src/components/Categorias.jsx`

- [ ] **Step 1: Update BarraProgreso in ResumenMes.jsx**

Find the `BarraProgreso` component at the top of the file. Change `height: 3` to `height: 4`:

```jsx
function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  const color = alerta ? 'var(--red)' : pct > 75 ? 'var(--orange)' : 'var(--accent)'
  return (
    <div style={{ background: 'var(--surface3)', borderRadius: 4, height: 4, width: '100%', marginTop: 5 }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.3s' }} />
    </div>
  )
}
```

- [ ] **Step 2: No change needed in Categorias.jsx**

`Categorias.jsx` does not render a progress bar — it shows spend vs budget as text only (`0.00€ / 50€`). The `BarraProgreso` component lives only in `ResumenMes.jsx`. Step 1 covers the only progress bar in the app.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ResumenMes.jsx frontend/src/components/Categorias.jsx
git commit -m "refactor: progress bar height 3px → 4px"
```

---

## Task 9: Final visual audit

**Files:** none

- [ ] **Step 1: Take screenshots of all views**

Using Playwright MCP, navigate to each view and screenshot:
- Resumen (with a past month selected that has data)
- Gastos
- Categorías
- Recurrentes
- Memoria
- Sidebar collapsed state

- [ ] **Step 2: Checklist**

Verify against spec success criteria:
- [ ] Sidebar renders, collapses, persists on refresh
- [ ] All 5 Finanzas views accessible via sidebar
- [ ] Logo mark (◈) visible in accent color
- [ ] Future modules (Automatizaciones, Herramientas) visible at 35% opacity, unclickable
- [ ] No horizontal tabs visible
- [ ] Gastos dates show as "dd MMM" format
- [ ] No regression in data display or mutations

- [ ] **Step 3: Commit screenshots to PR description or just verify inline**
