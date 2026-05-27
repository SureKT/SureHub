@echo off
cd /d "%~dp0"

:: Activar venv y arrancar backend
start /min "SureHub - Backend"  cmd /k "cd /d "%~dp0" && .venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8001"

:: Arrancar bot de Telegram
start /min "SureHub - Bot"      cmd /k "cd /d "%~dp0" && .venv\Scripts\activate && python -m bot.run"

:: Arrancar frontend
start /min "SureHub - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --port 5174"

:: Abrir navegador
start http://localhost:5174
