import { BarChart2, Zap, Wrench, Settings } from 'lucide-react'
import LogoMark from './LogoMark'

const MODULES = [
  {
    id: 'finance',
    label: 'Finance',
    icon: BarChart2,
    active: true,
    items: [
      { id: 'summary', label: 'Summary' },
      { id: 'expenses', label: 'Expenses' },
      { id: 'categories', label: 'Categories' },
      { id: 'recurring', label: 'Recurring' },
    ],
  },
  {
    id: 'automations',
    label: 'Automations',
    icon: Zap,
    active: false,
    items: [],
  },
  {
    id: 'tools',
    label: 'Tools',
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

      {/* Global footer: Memory + Settings */}
      {!collapsed && (
        <div style={{ borderTop: '1px solid var(--border-dim)', padding: '8px 0' }}>
          {['memory', 'settings'].map(id => {
            const label = id === 'memory' ? 'Memory' : 'Settings'
            const isActive = activeView === id
            return (
              <button
                key={id}
                onClick={() => onNavigate(id)}
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
              >{label}</button>
            )
          })}
        </div>
      )}

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
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
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
