# SureHub — TODO

Prioridad de arriba a abajo. Los módulos sin fecha son ideas capturadas, no comprometidas.

---

## En curso

- [x] **Spotify — frontend** ✓ — Spotify.jsx + Settings.jsx + light theme

---

## Próximo

- [ ] **Diario**
  - Registros libres (journal, reflexiones)
  - Logs estructurados con métricas variables (peso, mood, sueño, etc.)
    - Configuración en settings: añadir/quitar campos con nombre + tipo (número, texto, escala 1-10)
    - Reestructuración periódica — los campos cambian según objetivos
  - Categorías / colecciones — etiquetar entradas y navegar por colección
  - Timeline — colección especial de eventos vitales / grupo de amigos
  - Sin IA por ahora

---

## Pendiente

- [ ] **Calendario**
  - Google Calendar como backend
  - Claude gestiona eventos: añadir / modificar / eliminar via lenguaje natural
  - Colores por categoría configurables
  - Claude conoce historial de eventos (contexto personal)
  - Vista visor / resumen

- [ ] **Noticias**
  - Bandeja de entrada de noticias
  - Configurar temas de interés

- [ ] **Correo**
  - Gmail integration
  - Resumen de emails con Claude
  - Reglas (filtros, etiquetas)
  - Automatizaciones

- [ ] **Análisis documentos**
  - Ingesta de documentos (PDF, etc.)
  - Resumen con Claude
  - Automatizaciones basadas en contenido

---

## Finanzas — mejoras futuras

- [ ] Gráficos más ricos (evolución por categoría, comparativa meses)

---

## App shell — ideas futuras

- [ ] Login + gestión de credenciales / API keys de servicios externos
- [ ] Dual sidebar (izq: nav global · dcha: config módulo / explorar)
  - Explorar cuando los módulos tengan contenido secundario suficiente
  - Referencia: Coda.io, Notion, VSCode

---

## Infraestructura prod

- [ ] Hetzner VPS ~€4/mes
- [ ] Docker + docker-compose prod
- [ ] Webhook Telegram (cambiar `TELEGRAM_MODE`)
- [ ] Migrar SQLite → Postgres (`DATABASE_URL`)
