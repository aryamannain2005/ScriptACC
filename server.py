"""
ScriptACC – Central Command Gateway (C2 Server)
=================================================
FastAPI server with Groq Cloud (Llama-3.3-70B), Ollama, and OpenAI routing.
Optimized for corporate assessments (Accenture, MNCs) with specialized prompts.
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

TOKEN = cfg.get('token', 'YOUR_REGISTRATION_TOKEN')
LLM_PROVIDER = cfg.get('llm_provider', 'groq').lower()

# Groq Cloud (Free Llama-3.3-70B)
GROQ_KEY = os.environ.get('GROQ_API_KEY') or cfg.get('groq_api_key', '')
GROQ_MODEL = cfg.get('groq_model', 'llama-3.3-70b-versatile')

# Ollama Local (Fallback)
OLLAMA_ENDPOINT = cfg.get('ollama_endpoint', 'http://127.0.0.1:11434/api/generate')
OLLAMA_MODEL = cfg.get('ollama_model', 'llama3.2:3b')

# OpenAI (Fallback)
OPENAI_KEY = os.environ.get('OPENAI_API_KEY') or cfg.get('llm_api_key', '')
OPENAI_MODEL = cfg.get('llm_model', 'gpt-4o-mini')

# ── Mode-specific system prompts (Tuned for Accenture/MNC Assessments) ────────
SYSTEM_PROMPTS = {
    "mcq": (
        "You are an expert exam solver for corporate assessments (Accenture, CoCubes, Mettl, Wheebox).\n"
        "The user will provide screenshot OCR text containing multiple-choice questions, pseudocode, or aptitude.\n"
        "For EACH question:\n"
        "1. State the correct option clearly: 'Answer: [Option Letter/Number]' (e.g. 'Answer: B' or 'Answer: Option 3').\n"
        "2. Provide a crisp 1-2 line logical/mathematical trace (pay extreme attention to bitwise XOR/AND/OR, shifting, and loop boundaries in pseudocode).\n"
        "Be 100% accurate and concise. Output ONLY the answer and brief trace."
    ),
    "coding": (
        "You are a competitive programming champion for Accenture and MNC hiring rounds.\n"
        "The user provides OCR text from a coding challenge.\n"
        "1. Identify the problem, constraints, and standard input/output specifications.\n"
        "2. Provide the OPTIMAL, 100% correct solution in Python (or language shown) that passes ALL hidden test cases.\n"
        "3. Include clean standard input handling (e.g. sys.stdin.read or input()).\n"
        "4. Include Time & Space Complexity in the final line.\n"
        "Output clean code directly, no markdown fences if possible."
    ),
    "fullstack": (
        "You are a senior full-stack engineer and SQL expert for technical tests.\n"
        "1. If it's a SQL question, give the exact optimal query (handling JOINs, GROUP BY, window functions).\n"
        "2. If it's Web, Cloud, or API debugging, provide the direct code fix with a 1-line root cause explanation.\n"
        "Be direct, accurate, and concise."
    ),
    "game": (
        "You are a cognitive assessment and puzzle solver for hiring tests.\n"
        "Solve numerical series, logical deductions, syllogisms, or pattern reasoning step-by-step.\n"
        "State the final answer clearly in the first line."
    ),
    "general": (
        "You are an expert AI assistant. Analyze the provided screen text and give an accurate, concise answer."
    ),
}


# ── Request model ────────────────────────────────────────────────────────────
class ProcessRequest(BaseModel):
    token: str
    prompt: str
    mode: str = "general"


# ── LLM call functions ───────────────────────────────────────────────────────

async def call_groq(system_prompt: str, user_prompt: str) -> str:
    """Call Groq Cloud with ultra-fast Llama-3.3-70B."""
    if not GROQ_KEY:
        raise ValueError(
            "Groq API Key missing! Please paste your free key in config.yaml under 'groq_api_key' "
            "(Get one in 10s at https://console.groq.com/keys)"
        )
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
            },
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


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


# ── API endpoints ────────────────────────────────────────────────────────────

@app.post("/process")
async def process(req: ProcessRequest):
    if req.token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    system_prompt = SYSTEM_PROMPTS.get(req.mode, SYSTEM_PROMPTS["general"])

    try:
        if LLM_PROVIDER == 'groq':
            answer = await call_groq(system_prompt, req.prompt)
        elif LLM_PROVIDER == 'ollama':
            answer = await call_ollama(system_prompt, req.prompt)
        else:
            answer = await call_openai(system_prompt, req.prompt)
        return {"answer": answer, "mode": req.mode}
    except Exception as e:
        # Graceful fallback to Ollama if Groq is not configured or offline
        if LLM_PROVIDER == 'groq' and OLLAMA_ENDPOINT:
            try:
                print(f"  ⚠️ Groq error ({e}). Attempting local Ollama fallback...")
                answer = await call_ollama(system_prompt, req.prompt)
                return {"answer": answer, "mode": req.mode}
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "groq_configured": bool(GROQ_KEY),
        "groq_model": GROQ_MODEL,
        "ollama_model": OLLAMA_MODEL
    }
