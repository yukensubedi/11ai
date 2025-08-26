from fastapi import FastAPI, Body, Request,Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import requests, json
from fastapi.responses import JSONResponse
import logging

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = "http://ollama:11434"

# In-memory store for demo (later → DB per user)
conversations = {}


logger = logging.getLogger(__name__)



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error. Please try again later."},
    )

@app.post("/chat/{user_id}")
def chat(user_id: str, prompt: str = Body(..., embed=True)):
    # get previous messages
    history = conversations.get(user_id, [])
    # add new user message
    history.append({"role": "user", "content": prompt})

    def stream():
        with requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": "llama3",
                "messages": history,
                "stream": True
            },
            stream=True,
        ) as resp:
            resp.raise_for_status()
            assistant_reply = ""
            for line in resp.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        if "message" in chunk and "content" in chunk["message"]:
                            piece = chunk["message"]["content"]
                            assistant_reply += piece
                            yield piece
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

        # store assistant reply in history
        history.append({"role": "assistant", "content": assistant_reply})
        conversations[user_id] = history

    return StreamingResponse(stream(), media_type="text/plain")

import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

