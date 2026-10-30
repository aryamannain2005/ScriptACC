#!/usr/bin/env bash
# ==============================================================================
# ScriptACC – One-Click Zero-Permission Terminal Launcher (macOS)
# Usage: ./run.sh
# ==============================================================================

cd "$(dirname "$0")"

# 1. Check Python virtual environment
PYTHON_BIN=""
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

# 2. Start C2 Gateway server if not already alive
if ! curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "⚡ Starting ScriptACC Gateway server in background..."
    nohup "$PYTHON_BIN" -m uvicorn server:app --host 127.0.0.1 --port 8000 >server.log 2>&1 &
    sleep 1.5
fi

# 3. Launch Terminal Assistant
"$PYTHON_BIN" cli.py "$@"

