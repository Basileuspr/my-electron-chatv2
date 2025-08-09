# Electron + FastAPI Starter — v2.2b

Adds:
- Status pill (green/yellow/red)
- Model dropdown from Ollama `/api/tags`
- Backend hardened: no visible 500s, fallback from `/api/chat` to `/api/generate`
- `OLLAMA_TIMEOUT_SECONDS` default 90; `OLLAMA_NUM_PREDICT` to cap length
- In-memory conversation history per (conversation_id, model)

## Quick Start
1) Copy `backend\.env.example` → `backend\.env` and set your model (e.g., `gpt-oss:20b`).
2) Run:
```
.\scripts\start_app.bat
```
3) In the UI: select a model from the dropdown, check **Use Ollama**, and chat.
