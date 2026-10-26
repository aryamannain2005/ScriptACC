# ScriptACC – HostLab AI Assistant (macOS & Windows)

Automated screen capture, OCR, specialized mode routing, LLM reasoning, and translucent on-screen overlay + stealth auto-typing.

---

## ⚡ Architecture & Features

| Capability | Detail |
|---|---|
| **Local LLM Engine** | Ollama with `llama3.2:3b` (100% free, runs offline, zero API fees) |
| **Cloud LLM (Optional)** | OpenAI API compatible (`gpt-4o-mini`) via `config.yaml` |
| **C2 Server Gateway** | FastAPI with mode routing (`mcq`, `coding`, `fullstack`, `game`, `general`) |
| **High-Precision OCR** | Tesseract 5.5 (`brew install tesseract`) + PIL / PyAutoGUI |
| **Heads-Up Display** | PySide6 frameless translucent overlay HUD near mouse cursor (customizable opacity & dim mode) |
| **Stealth Typing** | Auto-Type and Ghost-Type with humanized delay variations & pause/resume controls |
| **Cross-Platform** | Native macOS client ([capture_ocr.py](file:///Users/aryamannain/ScriptACC/capture_ocr.py)) & Windows PowerShell loader ([launcher.ps1](file:///Users/aryamannain/ScriptACC/launcher.ps1)) |

---

## 🎹 Hotkey Cheat Sheet

> **Note on macOS**: `Option` is the `Alt` key. You can also use `Ctrl + Option + Key`.

| Hotkey | Mode / Action | Description |
|---|---|---|
| **Option + M** | **MCQ Solver** | Identifies question & options, returns the exact answer + 1-2 line explanation |
| **Option + 8** | **Coding / DSA Solver** | Generates optimal clean code solution + Time & Space complexity |
| **Option + 9** | **FullStack / Web / SQL** | Diagnoses bugs, writes SQL queries, provides API & framework solutions |
| **Option + 0** | **Game & Puzzle Solver** | Step-by-step logic puzzle and riddle breakdown |
| **Option + B** | **Add SS to Buffer** | Captures multiple screenshots into buffer (press M/8/9/0 to solve all combined) |
| **Option + F** | **Auto-Type** | Types the last generated solution directly into active code editor |
| **Option + G** | **Ghost-Type** | Stealth typing with randomized human keystroke intervals |
| **Option + R** | **Pause / Resume** | Pauses or resumes active typing |
| **Option + E** | **Emergency Stop** | Instantly stops typing |
| **Option + D** | **Show / Hide** | Toggles overlay visibility |
| **Option + N** | **Stealth Dim (9%)** | Reduces overlay opacity to barely visible 9% |
| **Option + I** | **Guide** | Displays quick hotkey HUD for 25s |
| **Option + Shift + X** | **Exit** | Shuts down client and listeners |

---

## 🚀 Quick Start (macOS)

### 1. Ensure Services Are Running
The background services run locally:
```bash
# 1. Ollama (if not already running)
ollama serve

# 2. FastAPI C2 Gateway
/opt/anaconda3/bin/uvicorn server:app --host 0.0.0.0 --port 8000
```

### 2. Start the HostLab macOS Client
```bash
/opt/anaconda3/bin/python capture_ocr.py
```

### 3. Usage Modes
- **With Accessibility Permission**: Press any global hotkey (e.g. `Option+8` or `Option+M`) while viewing any application.
- **Without Accessibility Permission**: In the terminal where `capture_ocr.py` is running, just press **ENTER** (defaults to Coding mode), or type `m`, `8`, `9`, `0`, `b`, `f`, `g`, `q`.

---

## 🔑 Granting macOS Accessibility Permissions (Optional for Global Hotkeys)

1. Open **System Settings** → **Privacy & Security** → **Accessibility**.
2. Click `+` and add your terminal application (**Terminal**, **iTerm2**, or **Visual Studio Code**).
3. Ensure the toggle next to it is **ON**.
