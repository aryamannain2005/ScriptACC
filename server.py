"""
ScriptACC – Central Command Gateway (C2 Server)
=================================================
FastAPI server with mode-based LLM routing.
Each hotkey mode uses a specialized system prompt.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yaml
import httpx

app = FastAPI(title="ScriptACC C2 Gateway")

# ── Load config ──────────────────────────────────────────────────────────────
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
with open(config_path, 'r') as f:
    cfg = yaml.safe_load(f)

TOKEN = cfg.get('token', '')
LLM_PROVIDER = cfg.get('llm_provider', 'ollama')
OLLAMA_ENDPOINT = cfg.get('ollama_endpoint', 'http://127.0.0.1:11434/api/generate')
OLLAMA_MODEL = cfg.get('ollama_model', 'llama3.2:3b')
OPENAI_KEY = cfg.get('llm_api_key', '')
OPENAI_MODEL = cfg.get('llm_model', 'gpt-4o-mini')

# ── Mode-specific system prompts ─────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "mcq": (
        "You are an expert MCQ solver. The user will provide a screenshot's OCR text "
        "containing one or more multiple-choice questions. For EACH question:\n"
        "1. Identify the question and all options.\n"
        "2. State the correct answer clearly (e.g., 'Answer: B').\n"
        "3. Give a brief 1-2 line explanation.\n"
        "Be concise. Output ONLY the answers, no filler text."
    ),
    "coding": (
        "You are an expert competitive programming and DSA solver. The user provides OCR text "
        "from a coding problem (LeetCode, HackerRank, Codeforces, etc.).\n"
        "1. Identify the problem.\n"
        "2. Provide the OPTIMAL solution in Python (or the language visible in the problem).\n"
        "3. Include time & space complexity.\n"
        "4. Keep the code clean, no comments unless tricky.\n"
        "Output the code directly — no markdown fences, no explanation unless asked."
    ),
    "fullstack": (
        "You are a senior full-stack engineer. The user provides OCR text from a web dev, "
        "SQL, API, or debugging problem.\n"
        "1. Identify what's being asked.\n"
        "2. Provide the direct solution (code, query, config, etc.).\n"
        "3. If it's a bug, explain the root cause in 1 line and give the fix.\n"
        "Be concise and practical."
    ),
    "game": (
        "You are a puzzle and game solver. The user provides OCR text from a logic puzzle, "
        "math problem, riddle, or game challenge.\n"
        "1. Solve it step by step.\n"
        "2. State the final answer clearly.\n"
        "Be concise."
    ),
    "general": (
        "You are an expert assistant. Analyze the provided screen text and give a helpful, "
        "concise response. If it contains a question, answer it directly."
    ),
}


# ── Request model ────────────────────────────────────────────────────────────
class ProcessRequest(BaseModel):
    token: str
    prompt: str
    mode: str = "general"  # mcq | coding | fullstack | game | general


# ── LLM call ─────────────────────────────────────────────────────────────────
async def call_ollama(system_prompt: str, user_prompt: str) -> str:
    """Call local Ollama model."""
    full_prompt = f"[System Instructions]\n{system_prompt}\n\n[User Input]\n{user_prompt}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            OLLAMA_ENDPOINT,
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
            }
        )
        resp.raise_for_status()
        return resp.json().get('response', '').strip()


async def call_openai(system_prompt: str, user_prompt: str) -> str:
    """Call OpenAI-compatible API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 2000,
                "temperature": 0.2,
            },
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


# ── API endpoint ─────────────────────────────────────────────────────────────
@app.post("/process")
async def process(req: ProcessRequest):
    # Token validation
    if req.token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    # Select system prompt based on mode
    system_prompt = SYSTEM_PROMPTS.get(req.mode, SYSTEM_PROMPTS["general"])

    try:
        if LLM_PROVIDER == 'ollama':
            answer = await call_ollama(system_prompt, req.prompt)
        else:
            answer = await call_openai(system_prompt, req.prompt)
        return {"answer": answer, "mode": req.mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "model": OLLAMA_MODEL, "provider": LLM_PROVIDER}
