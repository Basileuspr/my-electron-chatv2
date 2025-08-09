from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os, json, http.client

# Load .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    use_ollama: Optional[bool] = None
    model: Optional[str] = None

def _ollama_request(path: str, body: dict, timeout: int) -> tuple[int, str]:
    host = os.getenv("OLLAMA_HOST", "127.0.0.1")
    port = int(os.getenv("OLLAMA_PORT", "11434"))
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        payload = json.dumps(body)
        headers = {"Content-Type": "application/json"}
        print(f"[OLLAMA] -> http://{host}:{port}{path} bodyKeys={list(body.keys())}")
        conn.request("POST", path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="ignore")
        print(f"[OLLAMA] status={resp.status} bytes={len(raw)} snippet={raw[:200]!r}")
        return resp.status, raw
    finally:
        try:
            conn.close()
        except Exception:
            pass

def try_ollama_chat(prompt: str, model_override: Optional[str] = None) -> Optional[str]:
    """
    Use /api/chat with messages format.
    """
    model = model_override or os.getenv("OLLAMA_MODEL", "chatgpt-oss:20b")
    timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    status, raw = _ollama_request(
        "/api/chat",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        },
        timeout,
    )
    if status != 200:
        return None
    try:
        data = json.loads(raw or "{}")
        msg = data.get("message") or {}
        return msg.get("content")
    except Exception as e:
        print(f"[OLLAMA] parse error: {e}")
        return None

def warmup_model_if_enabled() -> None:
    env_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() in ("1", "true", "yes")
    if not env_enabled:
        return
    model = os.getenv("OLLAMA_MODEL", "chatgpt-oss:20b")
    try:
        print(f"[OLLAMA] warmup for model={model!r}")
        _ = try_ollama_chat("warmup", model_override=model)
    except Exception as e:
        print(f"[OLLAMA] warmup failed: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    # optional warmup so first request is faster
    warmup_model_if_enabled()

@app.post("/chat")
def chat(req: ChatRequest):
    user_msg = (req.message or "").strip()
    if not user_msg:
        return {"response": "[Empty prompt]"}

    env_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() in ("1", "true", "yes")
    should_use_ollama = bool(req.use_ollama) if req.use_ollama is not None else env_enabled

    if should_use_ollama:
        reply = try_ollama_chat(user_msg, model_override=req.model)
        if reply:
            return {"response": reply}

    return {"response": f"(local fallback) You said: {user_msg}"}
