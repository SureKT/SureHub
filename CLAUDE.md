# SureHub

Plataforma personal modular: finanzas, noticias, automatizaciones, agente IA.
Usuario único: Sure (uso doméstico, sin auth, sin multiusuario).
Stack: FastAPI + SQLModel + SQLite/Postgres + Telegram bot + Claude API.

## Comandos
- Backend: `uvicorn app.main:app --reload` (desde raíz, venv activado)
- Bot: `python -m bot.run` (segunda terminal, venv activado)
- Frontend: `cd frontend && npm run dev` (tercera terminal)
- Scripts puntuales: `python scripts/<script>.py` (desde raíz, venv activado)

## Estructura
```
app/
  modules/<modulo>/
    models.py    # SQLModel table models
    service.py   # lógica de negocio, recibe Session
    parser.py    # parsing de input (si aplica)
  services/
    llm.py       # wrapper Claude API
  routers/
    finanzas.py  # endpoints REST del módulo finanzas
  config.py      # Settings desde .env
  database.py    # engine, get_session, create_db
  models.py      # importa todos los modelos (para create_db)
  main.py        # FastAPI app
bot/
  handlers.py    # handlers de Telegram
  run.py         # arranque del bot (llama a create_db al inicio)
frontend/        # React + Vite, proxy /api → localhost:8001
scripts/         # scripts de migración y seed (uso puntual, no producción)
```

## Convenciones
- Código en inglés: modelos, servicios, routers, frontend, API keys, labels UI
- Bot Telegram: respuestas en español (Sure habla español con el bot)
- Nuevos módulos siempre en `app/modules/<module>/` con models + service
- Registrar modelo nuevo en `app/models.py` para que create_db() lo cree
- `get_session()` con `next()` en handlers — no usar como context manager en sync code
- Variables de entorno: siempre en `.env`, nunca hardcodeadas, documentar en `.env.example`
- Sin comentarios obvios — solo si el WHY no es evidente
- Migraciones de DB: SQLite soporta ALTER TABLE ADD COLUMN sin perder datos. Para cambios mayores, script en `scripts/`

## Commits
- Ejecutar commit automáticamente (sin pedir permiso) cuando:
  - El usuario confirma que algo funciona ("funciona", "listo", "perfecto", "ok")
  - Y hay cambios suficientes (feature completa, fix real, módulo nuevo)
- NO commitear por cambios triviales (un typo, un print de debug, ajuste de texto)
- Mensajes en inglés, formato: `<tipo>: <qué> + detalle en body si aplica`
- Tipos: `feat`, `fix`, `refactor`, `chore`

## Decisiones de arquitectura
- SQLite en local, Postgres en prod — cambio solo en DATABASE_URL
- Telegram polling en local, webhook en prod — cambio en TELEGRAM_MODE
- Bot y FastAPI corren como procesos separados en local, mismo container en prod
- Claude API model: `claude-sonnet-4-6` — cambiar solo si hay razón explícita
- No hay historial de conversación en el bot — cada mensaje es independiente (decisión consciente, añadir si el uso real lo justifica)
- Memoria del bot: manual vía /recuerda. Se inyecta en system prompt de Claude
- Frontend consume API en /api (proxy Vite → FastAPI). En prod, mismo origen

## Estado actual del módulo Finanzas
- Modelos: `Category` (name, type, monthly_estimate, active) + `Expense` (category_id FK, amount, description, date, source) + `RecurringExpense` (name, amount, category_id, day, active)
- `Category.active`: soft delete — inactive categories hidden in UI but historical expenses keep FK
- Inactive categories: Anillo, Ahorros (historical data from Coda)
- 482 historical expenses imported from Coda (June 2025 → March 2026)
- Telegram parser detects "description amount" or "amount description" pattern, infers category by keywords
- Import source values: `telegram`, `manual`, `import`, `recurring`
- API prefix: `/api/finance` (categories, expenses, summary, evolution, months, import)
- Ports: backend 8001, frontend 5174

## Infraestructura objetivo
- Local ahora: PC + 3 terminales (backend, bot, frontend)
- Prod futuro: Hetzner VPS ~€4/mes, Docker, webhook Telegram, Postgres
- Claude API: ~$5-15/mes uso personal moderado

---

## UI — Design System

El frontend usa la skill `ui-ecosystem`. Antes de cualquier cambio visual, aplicar sus reglas sin excepciones.

### Flujo obligatorio para cambios de UI

**Nunca implementar cambios visuales sin seguir este flujo:**

1. **Audit visual primero** — antes de proponer nada, tomar screenshots de la vista con Playwright e identificar qué la hace parecer inacabada: no solo violaciones de tokens sino criterio de acabado (elemento focal, jerarquía, estados vacíos, peso relativo de controles). Si el cambio afecta múltiples vistas, hacer el audit de todas antes de tocar código.
2. **Proponer antes de codificar** — escribir en texto qué elemento se va a cambiar, por qué viola el design system o los criterios de acabado, y qué solución se va a aplicar. Incluir boceto ASCII si el cambio es estructural. Esperar confirmación.
3. **Un componente a la vez** — no refactorizar múltiples vistas en un solo paso.
4. **Autoevaluar al terminar** — tomar screenshot con Playwright, ejecutar el checklist del SKILL.md y reportar resultado.

Formato de reporte al terminar un cambio:
```
✅ Cambio: [qué se cambió]
📐 Regla aplicada: [qué regla del SKILL.md]
🔍 Checklist: [items verificados]
⚠️ Pendiente: [qué no se ha tocado todavía]
```

### Reglas inamovibles de UI

1. **Cero azul eléctrico** — no usar `blue-*` de Tailwind. El único acento es `--accent` (#c8f0dc).
2. **Listas = filas planas** — listas de más de 3 items usan filas con `border-b`, no cards individuales con `rounded-xl` por item.
3. **Un acento por vista** — `--accent` aparece en máximo un elemento por página.
4. **El dato más importante manda** — totales y valores clave: mínimo `text-4xl font-light`, no dentro de cards pequeñas.
5. **Badges de categoría: grises** — `bg-subtle text-muted`, nunca colores de acento.
6. **Sin date pickers nativos** — `<input type="date">` solo con reset de estilos completo o componente custom.
7. **Jerarquía tipográfica en 3 niveles**:
   - Label/sección: `text-xs uppercase tracking-wide text-faint`
   - Contenido principal: `text-sm text-primary`
   - Metadata/secundario: `text-xs text-muted`

### Criterios de acabado — checklist obligatorio

**1. Elemento focal por vista**
Cada vista tiene UN dato tipográficamente dominante (≥28px, font-weight 300) que responde la pregunta principal del usuario. Resumen → total gastado. Recurrentes → total mensual. Si el dato más importante no salta a la vista en 2 segundos, la vista no está terminada.

**2. Estados vacíos diseñados**
Ningún estado vacío puede ser solo texto. Mínimo: texto `--text-muted` centrado + descripción `text-xs`. Óptimo: icono outline 32px `--text-muted` + título + descripción. Nunca mostrar "Sin X" suelto en pantalla en blanco.

**3. Sin texto de onboarding permanente**
Las frases descriptivas de qué hace una vista ("Gastos que se generan...") deben eliminarse. Si la UI es autoexplicativa, el texto sobra. Si hace falta contexto, va en tooltip o primera visita — nunca como párrafo fijo visible siempre.

**4. Jerarquía de controles en formularios**
Si una vista tiene formulario de creación + controles de filtro/acción, deben tener diferente peso visual. El formulario de creación es bloque primario (más espacio, separado visualmente). Los filtros son secundarios (más compactos, menos contraste). Nunca iguales.

**5. Hover states en todo elemento interactivo**
Botones ghost, filas de lista, textos editables: todos deben tener hover visible. Mínimo: `background: var(--surface3)` en hover. Sin hover = el elemento parece roto o decorativo.

**6. IDs técnicos nunca visibles**
No mostrar IDs de base de datos al usuario (ej. `#1`, `#42`). Si se necesita identificador, usar orden ordinal contextual o campo semántico.

### Prioridad de mejoras UI pendientes
~~Todas completadas.~~ ✅ Design system aplicado en todas las vistas.

### Lo que NO hacer en UI
- No usar criterio estético propio — usar el SKILL.md
- No "mejorar" elementos que no se han pedido
- No refactorizar CSS global sin avisar
- No cambiar la paleta de colores definida en el SKILL.md
- No usar librerías de componentes externas (MUI, Chakra, etc.) sin preguntar

---

## Plugins de Claude Code

Plugins instalados globalmente en esta máquina. Si hay que reinstalar en una máquina nueva:

### superpowers
Skills para TDD, debugging, brainstorming, patrones de desarrollo.

**Instalar (método manual — `/plugin` no funciona en modo agente):**
```powershell
git clone https://github.com/obra/superpowers.git "$env:TEMP\superpowers-tmp"
$src = "$env:TEMP\superpowers-tmp\skills"
$dst = "$env:USERPROFILE\.claude\skills"
Get-ChildItem $src -Directory | ForEach-Object {
  New-Item -ItemType Directory -Force "$dst\$($_.Name)" | Out-Null
  Copy-Item "$src\$($_.Name)\SKILL.md" "$dst\$($_.Name)\SKILL.md" -Force
}
```
Skills instalados: brainstorming, executing-plans, subagent-driven-development, systematic-debugging, test-driven-development, writing-plans, y más.
Repo: https://github.com/obra/superpowers

### caveman
Modo de comunicación ultra-comprimido (~65-75% menos tokens). Activa con `/caveman` o "caveman mode".

**Instalar (Windows):**
```powershell
$tmp = "$env:TEMP\caveman-install.ps1"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.ps1" -OutFile $tmp
& $tmp
```
Luego copiar los SKILL.md a `~/.claude/skills/`:
```powershell
$base = "$env:USERPROFILE\.claude\skills"
$src = "<ruta-donde-corriste-el-instalador>\.agents\skills"
foreach ($s in @("caveman","cavecrew","caveman-commit","caveman-compress","caveman-help","caveman-review","caveman-stats")) {
  New-Item -ItemType Directory -Force "$base\$s" | Out-Null
  Copy-Item "$src\$s\SKILL.md" "$base\$s\SKILL.md" -Force
}
```
Repo: https://github.com/juliusbrussee/caveman