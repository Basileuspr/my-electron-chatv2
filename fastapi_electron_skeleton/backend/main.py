from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Tuple, Deque, Dict, List
import os, json, http.client
from collections import defaultdict, deque

# Load .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Print effective config (helps diagnose)
print("[CFG] OLLAMA_ENABLED=", os.getenv("OLLAMA_ENABLED"))
print("[CFG] OLLAMA_HOST=", os.getenv("OLLAMA_HOST"))
print("[CFG] OLLAMA_PORT=", os.getenv("OLLAMA_PORT"))
print("[CFG] OLLAMA_MODEL=", os.getenv("OLLAMA_MODEL"))
print("[CFG] TIMEOUT=", os.getenv("OLLAMA_TIMEOUT_SECONDS"))

app = FastAPI()

# Global exception handler -> friendly JSON instead of 500
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    print(f"[BACKEND] Unhandled Exception: {exc}")
    return JSONResponse(status_code=200, content={
        "response": "(local fallback) [internal error handled]",
        "meta": {"used_ollama": False, "error": str(exc)[:200]}
    })

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
    conversation_id: Optional[str] = None

# In-memory: (conversation_id, model) -> deque of messages
HISTORY_MAX_TURNS = int(os.getenv("HISTORY_MAX_TURNS", "16"))
HISTORIES: Dict[Tuple[str, str], Deque[Dict]] = defaultdict(lambda: deque(maxlen=HISTORY_MAX_TURNS))

def _ollama_request(path: str, body: dict, timeout: int) -> tuple[int, str]:
    host = os.getenv("OLLAMA_HOST", "127.0.0.1")
    port = int(os.getenv("OLLAMA_PORT", "11434"))
    try:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)
        payload = json.dumps(body)
        headers = {"Content-Type": "application/json"}
        print(f"[OLLAMA] -> http://{host}:{port}{path} keys={list(body.keys())}")
        conn.request("POST", path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="ignore")
        print(f"[OLLAMA] status={resp.status} bytes={len(raw)} snippet={raw[:200]!r}")
        return resp.status, raw
    except Exception as e:
        msg = f'{{"error":"{type(e).__name__}: {str(e)[:180]}"}}'
        print(f"[OLLAMA] EXC: {e}")
        return 599, msg
    finally:
        try:
            conn.close()
        except Exception:
            pass

def try_ollama_generate(prompt: str, model_override: Optional[str] = None) -> Optional[str]:
    model = model_override or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))
    status, raw = _ollama_request(
        "/api/generate",
        {"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": num_predict}},
        timeout,
    )
    if status != 200:
        return None
    try:
        data = json.loads(raw or "{}")
        return data.get("response")
    except Exception as e:
        print(f"[OLLAMA] generate parse error: {e}")
        return None

def try_ollama_chat_with_history(messages: List[Dict], model_override: Optional[str] = None) -> Optional[str]:
    model = model_override or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
    num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "256"))

    # First attempt: /api/chat
    status, raw = _ollama_request(
        "/api/chat",
        {"model": model, "messages": messages, "stream": False, "options": {"num_predict": num_predict}},
        timeout,
    )
    if status == 200:
        try:
            data = json.loads(raw or "{}")
            msg = data.get("message") or {}
            content = (msg.get("content") or "").strip()
            if content:
                return content
            else:
                print("[OLLAMA] empty content from /api/chat; will fallback to /api/generate")
        except Exception as e:
            print(f"[OLLAMA] chat parse error: {e}")

    # Fallback: /api/generate (serialize messages → prompt)
    prompt_lines = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        prompt_lines.append(f"{role.capitalize()}: {content}")
    prompt_lines.append("Assistant:")
    prompt = "\n".join(prompt_lines)

    return try_ollama_generate(prompt, model_override=model)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/models")
def models():
    """Return available model names from Ollama /api/tags; tolerate failures."""
    host = os.getenv("OLLAMA_HOST", "127.0.0.1")
    port = int(os.getenv("OLLAMA_PORT", "11434"))
    names: List[str] = []
    try:
        conn = http.client.HTTPConnection(host, port, timeout=10)
        conn.request("GET", "/api/tags")  # <-- GET (not POST)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="ignore")
        print(f"[OLLAMA] GET /api/tags status={resp.status} bytes={len(raw)}")
        if resp.status == 200:
            data = json.loads(raw or "{}")
            for item in (data.get("models") or []):
                name = item.get("name")
                if name:
                    names.append(name)
    except Exception as e:
        print(f"[OLLAMA] /api/tags error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"models": names}

@app.post("/chat")
def chat(req: ChatRequest):
    user_msg = (req.message or "").strip()
    if not user_msg:
        return {"response": "[Empty prompt]", "meta": {"used_ollama": False}}

    env_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() in ("1", "true", "yes")
    should_use_ollama = bool(req.use_ollama) if req.use_ollama is not None else env_enabled

    model = req.model or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
    conv_id = req.conversation_id or "default"
    key = (conv_id, model)

    if should_use_ollama:
        history = HISTORIES[key]
        history.append({"role": "user", "content": user_msg})
        reply = try_ollama_chat_with_history(list(history), model_override=model)
        if reply:
            history.append({"role": "assistant", "content": reply})
            return {"response": reply, "meta": {"used_ollama": True}}

    return {"response": f"(local fallback) You said: {user_msg}", "meta": {"used_ollama": False}}