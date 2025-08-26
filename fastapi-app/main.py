import os
import sys
import uuid
import logging
import contextvars
from typing import AsyncGenerator

import requests
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError

from exceptions import SubscriptionLimitExceeded, RateLimitExceeded, ExternalServiceError
from rate_limit import incr_usage

# --------- Logging config (structured + request id) ----------
request_id_var = contextvars.ContextVar("request_id", default="-")

class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")

formatter = logging.Formatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","request_id":"%(request_id)s","message":"%(message)s"}'
    if LOG_FORMAT == "json"
    else "[%(asctime)s] [%(levelname)s] [%(name)s] [rid=%(request_id)s] %(message)s"
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
handler.addFilter(RequestIDFilter())
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)
root_logger.handlers = [handler]

logger = logging.getLogger(__name__)

# --------- App ----------
app = FastAPI()

# CORS (adjust for your domain in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Request ID middleware ----------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request_id_var.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response

# --------- JWT auth (Django SimpleJWT) ----------
JWT_AUDIENCE = os.getenv("JWT_AUD", None)  # optional
JWT_ALG = os.getenv("JWT_ALG", "HS256")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")  # set this to Django SIMPLE_JWT['SIGNING_KEY']

def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], audience=JWT_AUDIENCE)
        return {"user_id": str(payload.get("user_id") or payload.get("user", "")), "email": payload.get("email")}
    except JWTError as e:
        logger.warning("Invalid JWT: %s", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")

# --------- Global exception handling ----------
@app.exception_handler(SubscriptionLimitExceeded)
async def handle_sub_limit(_: Request, exc: SubscriptionLimitExceeded):
    logger.warning("Subscription limit: %s", str(exc))
    return JSONResponse(status_code=402, content={"error": str(exc), "request_id": request_id_var.get()})

@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit(_: Request, exc: RateLimitExceeded):
    logger.warning("Rate limited: %s", str(exc))
    return JSONResponse(status_code=429, content={"error": str(exc), "request_id": request_id_var.get()})

@app.exception_handler(ExternalServiceError)
async def handle_ext(_: Request, exc: ExternalServiceError):
    logger.error("Upstream error: %s", str(exc))
    return JSONResponse(status_code=502, content={"error": "Upstream unavailable", "request_id": request_id_var.get()})

@app.exception_handler(Exception)
async def handle_all(_: Request, exc: Exception):
    logger.error("Unhandled error: %s", str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "request_id": request_id_var.get()})

# --------- AI chat endpoint (stream) ----------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

def enforce_plan_and_rate(user_id: str) -> None:
    """
    Example: pull a per-user quota from env or default (hook this to DB later).
    For demo, Free = 100/day. Replace with a lookup via Django API/DB if needed.
    """
    per_day_limit = int(os.getenv("DAILY_MESSAGE_LIMIT", "100"))
    current, limit = incr_usage(user_id, per_day_limit)
    logger.info("usage %s: %s/%s", user_id, current, limit)

@app.post("/chat")
async def chat(payload: dict, user=Depends(get_current_user)):
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "Prompt is required"})

    # Quota checks
    enforce_plan_and_rate(user_id=user["user_id"])

    # Stream from Ollama
    try:
        def gen() -> AsyncGenerator[bytes, None]:
            with requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": os.getenv("OLLAMA_MODEL", "llama3"), "prompt": prompt, "stream": True},
                stream=True,
                timeout=60,
            ) as resp:
                if resp.status_code >= 400:
                    raise ExternalServiceError(f"Ollama error {resp.status_code}: {resp.text[:200]}")
                for chunk in resp.iter_lines(decode_unicode=True):
                    if chunk:
                        # You can parse JSON chunks; here we just emit text content if present
                        yield chunk.encode("utf-8") + b"\n"
        return StreamingResponse(gen(), media_type="text/plain")
    except requests.RequestException as e:
        raise ExternalServiceError(str(e))
