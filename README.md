# Electron + FastAPI Starter (Port 8000) — v1.2.1

Updates from v2:
- Backend uses **/api/chat** (chat format) with **verbose logs**
- **Warmup on startup** if `OLLAMA_ENABLED=true` in `.env`
- Keep UI toggle + model field, .env support, and one-click launcher

## Quick Start (Windows)
```powershell
.\scripts\start_app.bat
```
- If `backend\.env` has `OLLAMA_ENABLED=true`, the launcher will
  - ensure Ollama is running,
  - warm the configured model via `/api/chat`,
  - then launch Electron (which spawns FastAPI).
- In the UI, you can still override per message with **Use Ollama** and by typing a model name.

## Logs
- The backend prints `[OLLAMA] ...` lines so you can confirm requests hit your local server and see status codes/snippets.

## .env
See `backend\.env.example` and copy to `backend\.env` to customize:
```
OLLAMA_ENABLED=true
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434
OLLAMA_MODEL=chatgpt-oss:20b
OLLAMA_TIMEOUT_SECONDS=60
```
