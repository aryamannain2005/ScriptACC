#!/usr/bin/env python3
"""
ScriptACC – Zero-Permission Terminal AI Assistant
==================================================
Runs 100% inside your terminal with ZERO macOS Accessibility permissions required!

Features:
  - Native screencapture on macOS (instant 0.1s capture)
  - Tesseract OCR extraction
  - Direct Groq Cloud AI Solver (120B Model)
  - Automatic clipboard copy (Cmd+V / Ctrl+V to paste instantly)
  - Native macOS Notification banner
  - Switch delay option (2s countdown to switch to your test tab)
  - Multi-screenshot buffer support
"""

import os
import sys
import time
import subprocess
import yaml
import httpx
from PIL import Image
import pytesseract

# ── Color Palette ─────────────────────────────────────────────────────────────
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

# ── Paths & Config ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.yaml')
SERVER_URL = "http://127.0.0.1:8000/process"
HEALTH_URL = "http://127.0.0.1:8000/health"

cfg = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r') as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        pass

TOKEN = cfg.get('token', 'YOUR_REGISTRATION_TOKEN')
OCR_LANG = cfg.get('ocr_language', 'eng')

# ── State ─────────────────────────────────────────────────────────────────────
class State:
    last_answer = ""
    buffer_images = []
    switch_delay = 2  # Seconds to wait before capture so user can switch window

state = State()


# ── Server Health & Auto-Start ────────────────────────────────────────────────
def ensure_server():
    """Verify local C2 server is responding; auto-start if down."""
    try:
        r = httpx.get(HEALTH_URL, timeout=1.5)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    print(f"{Colors.YELLOW}[*] Starting background C2 server gateway...{Colors.END}")
    server_script = os.path.join(BASE_DIR, 'server.py')
    log_file = os.path.join(BASE_DIR, 'server.log')
    err_file = os.path.join(BASE_DIR, 'server_err.log')
    
    with open(log_file, 'a') as out, open(err_file, 'a') as err:
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=BASE_DIR,
            stdout=out,
            stderr=err,
            start_new_session=True
        )

    for _ in range(12):
        time.sleep(0.5)
        try:
            r = httpx.get(HEALTH_URL, timeout=1.5)
            if r.status_code == 200:
                print(f"{Colors.GREEN}[+] C2 server is active and verified!{Colors.END}")
                return True
        except Exception:
            pass

    print(f"{Colors.RED}[!] Could not verify server on port 8000. Will attempt direct fallback.{Colors.END}")
    return False


# ── Clipboard & Notification ──────────────────────────────────────────────────
def copy_to_clipboard(text: str):
    """Copy answer to system clipboard (Cmd+V on Mac / Ctrl+V on Windows)."""
    try:
        if sys.platform == 'darwin':
            p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
            p.communicate(text.encode('utf-8'))
            return True
        elif sys.platform == 'win32':
            p = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
            p.communicate(text.encode('utf-8'))
            return True
        else:
            p = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
            p.communicate(text.encode('utf-8'))
            return True
    except Exception:
        return False


def notify(title: str, message: str):
    """Show native macOS notification."""
    if sys.platform == 'darwin':
        try:
            # Escape quotes
            safe_msg = message.replace('"', '\\"').replace('\n', ' ')[:100]
            safe_title = title.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


# ── Screen Capture (Zero Accessibility Permission) ───────────────────────────
def capture_screen_image() -> Image.Image:
    """Capture screen without needing macOS Accessibility or PySide6 WindowServer."""
    temp_img = os.path.join('/tmp' if sys.platform != 'win32' else os.environ.get('TEMP', '.'), f'scriptacc_cap_{int(time.time()*1000)}.png')
    
    if sys.platform == 'darwin':
        # Native screencapture CLI: 100% reliable, zero Accessibility hook needed!
        res = subprocess.run(['screencapture', '-x', temp_img])
        if res.returncode == 0 and os.path.exists(temp_img):
            img = Image.open(temp_img).convert('RGB')
            try:
                os.remove(temp_img)
            except Exception:
                pass
            return img

    # Fallback for Windows or Linux
    try:
        import pyautogui
        return pyautogui.screenshot()
    except Exception:
        from PIL import ImageGrab
        return ImageGrab.grab()


def run_ocr(img: Image.Image) -> str:
    """Run OCR extraction."""
    # Windows native WinOCR check
    if sys.platform == 'win32':
        try:
            import winocr
            res = winocr.recognize_pil_sync(img)
            if hasattr(res, 'text'):
                t = str(res.text).strip()
            elif isinstance(res, dict):
                t = str(res.get('text', '')).strip()
            else:
                t = str(res).strip()
            if t:
                return t
        except Exception:
            pass

    # Tesseract OCR
    try:
        return pytesseract.image_to_string(img, lang=OCR_LANG).strip()
    except Exception as e:
        print(f"{Colors.RED}  [!] OCR error: {e}{Colors.END}")
        return ""


# ── Solve Mode ────────────────────────────────────────────────────────────────
def solve(mode: str = "coding"):
    mode_titles = {
        "coding": "💻 Coding Solver (DSA / Hidden Test Cases)",
        "mcq": "🎯 Multi-MCQ Solver (Accenture / MNC Aptitude)",
        "fullstack": "🌐 FullStack / SQL / Bug Fix Solver",
        "game": "🧩 Cognitive / Pattern / Syllogism Solver",
    }
    title = mode_titles.get(mode, f"AI Solver ({mode})")

    print(f"\n{Colors.CYAN}{'═' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{title}{Colors.END}")
    print(f"{Colors.CYAN}{'═' * 60}{Colors.END}")

    # Delay to let user switch to their browser/exam tab
    if state.switch_delay > 0 and not state.buffer_images:
        print(f"{Colors.YELLOW}⏳ Switching to exam window in {state.switch_delay}s... Focus your browser now!{Colors.END}")
        for sec in range(state.switch_delay, 0, -1):
            print(f"  {sec}...", end=" ", flush=True)
            time.sleep(1)
        print()

    # Capture
    print(f"{Colors.CYAN}📸 Capturing screen...{Colors.END}")
    t0 = time.time()
    
    if state.buffer_images:
        print(f"{Colors.YELLOW}📋 Processing {len(state.buffer_images)} buffered screenshots...{Colors.END}")
        texts = []
        for i, bimg in enumerate(state.buffer_images):
            txt = run_ocr(bimg)
            if txt:
                texts.append(txt)
        screen_text = "\n\n---\n\n".join(texts)
        state.buffer_images.clear()
    else:
        img = capture_screen_image()
        screen_text = run_ocr(img)

    if not screen_text or len(screen_text.strip()) < 5:
        print(f"{Colors.RED}⚠️ No readable text detected on screen! Ensure question is visible.{Colors.END}")
        print(f"{Colors.YELLOW}Tip: Check System Settings > Privacy & Security > Screen Recording if on macOS.{Colors.END}")
        return

    print(f"{Colors.GREEN}🔍 Extracted {len(screen_text)} characters in {time.time()-t0:.2f}s{Colors.END}")
    print(f"{Colors.CYAN}⚡ Querying Groq Cloud Llama-120B...{Colors.END}")

    # Send to Server
    t_api = time.time()
    answer = ""
    try:
        resp = httpx.post(
            SERVER_URL,
            json={'token': TOKEN, 'prompt': screen_text, 'mode': mode},
            timeout=90.0
        )
        if resp.status_code == 200:
            answer = resp.json().get('answer', '')
        else:
            answer = f"Error {resp.status_code}: {resp.text}"
    except Exception as e:
        answer = f"Connection Error: {e}"

    dur = time.time() - t_api
    state.last_answer = answer

    # Display Answer in Terminal
    print(f"\n{Colors.BOLD}{Colors.GREEN}══════════════════════ SOLUTION ({dur:.2f}s) ══════════════════════{Colors.END}\n")
    print(f"{Colors.BOLD}{answer}{Colors.END}")
    print(f"\n{Colors.BOLD}{Colors.GREEN}═══════════════════════════════════════════════════════════════════{Colors.END}")

    # Copy to Clipboard automatically!
    if copy_to_clipboard(answer):
        print(f"{Colors.YELLOW}📋 Copied to clipboard! Just press {Colors.BOLD}{'Cmd+V' if sys.platform=='darwin' else 'Ctrl+V'}{Colors.END}{Colors.YELLOW} in your editor/browser!{Colors.END}")
        notify("ScriptACC Solution Ready", answer[:80] + "...")
    print("\a", end="")  # System chime/beep


def add_to_buffer():
    """Add a screenshot to multi-page buffer."""
    if state.switch_delay > 0:
        print(f"{Colors.YELLOW}⏳ Switching in {state.switch_delay}s...{Colors.END}")
        time.sleep(state.switch_delay)
    img = capture_screen_image()
    state.buffer_images.append(img)
    count = len(state.buffer_images)
    print(f"{Colors.GREEN}📋 Screenshot added to buffer (Total: {count}). Press [1] or [2] to solve combined!{Colors.END}")


# ── Interactive Menu ──────────────────────────────────────────────────────────
def interactive_loop():
    while True:
        delay_label = f"{state.switch_delay}s countdown" if state.switch_delay > 0 else "Instant (0s)"
        buffer_label = f" ({len(state.buffer_images)} stored)" if state.buffer_images else ""

        print(f"\n{Colors.CYAN}┌──────────────────────────────────────────────────────────┐{Colors.END}")
        print(f"{Colors.CYAN}│{Colors.BOLD}{Colors.GREEN}       ScriptACC Zero-Permission Terminal Assistant       {Colors.END}{Colors.CYAN}│{Colors.END}")
        print(f"{Colors.CYAN}└──────────────────────────────────────────────────────────┘{Colors.END}")
        print(f" {Colors.BOLD}[ENTER]{Colors.END} or {Colors.BOLD}[1]{Colors.END}  ➔  {Colors.GREEN}Coding / DSA Solver{Colors.END} (Hidden Test Cases)")
        print(f" {Colors.BOLD}[2]{Colors.END} or {Colors.BOLD}[m]{Colors.END}      ➔  {Colors.GREEN}Multi-MCQ Solver{Colors.END} (Accenture / MNC Aptitude)")
        print(f" {Colors.BOLD}[3]{Colors.END} or {Colors.BOLD}[s]{Colors.END}      ➔  {Colors.GREEN}FullStack / SQL / Bug Fix{Colors.END}")
        print(f" {Colors.BOLD}[4]{Colors.END} or {Colors.BOLD}[p]{Colors.END}      ➔  {Colors.GREEN}Game / Cognitive / Syllogisms{Colors.END}")
        print(f" {Colors.BOLD}[b]{Colors.END}          ➔  {Colors.YELLOW}Add Screenshot to Buffer{buffer_label}{Colors.END}")
        print(f" {Colors.BOLD}[d]{Colors.END}          ➔  {Colors.CYAN}Toggle Switch Delay{Colors.END} [Current: {delay_label}]")
        print(f" {Colors.BOLD}[c]{Colors.END}          ➔  {Colors.CYAN}Re-Copy Last Answer to Clipboard{Colors.END}")
        print(f" {Colors.BOLD}[q]{Colors.END}          ➔  {Colors.RED}Quit{Colors.END}")
        print(f"{Colors.DIM}────────────────────────────────────────────────────────────{Colors.END}")

        try:
            choice = input(f"{Colors.BOLD}Select action [ENTER=Coding]: {Colors.END}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Exiting ScriptACC. Goodbye!{Colors.END}")
            break

        if choice in ['', '1', 'c', 'coding']:
            if choice == 'c' and state.last_answer:
                copy_to_clipboard(state.last_answer)
                print(f"{Colors.GREEN}📋 Re-copied last answer to clipboard!{Colors.END}")
            else:
                solve("coding")
        elif choice in ['2', 'm', 'mcq']:
            solve("mcq")
        elif choice in ['3', 's', 'sql', 'fullstack']:
            solve("fullstack")
        elif choice in ['4', 'p', 'game']:
            solve("game")
        elif choice == 'b':
            add_to_buffer()
        elif choice == 'd':
            state.switch_delay = 0 if state.switch_delay > 0 else 2
            print(f"{Colors.GREEN}[+] Delay set to: {state.switch_delay} seconds{Colors.END}")
        elif choice == 'q':
            print(f"{Colors.YELLOW}Exiting ScriptACC. Goodbye!{Colors.END}")
            break
        else:
            print(f"{Colors.RED}Unknown choice. Press ENTER for Coding, 2 for MCQ, b for buffer, q to quit.{Colors.END}")


# ── Main Entrypoint ───────────────────────────────────────────────────────────
def main():
    ensure_server()

    # CLI flag shortcuts (e.g. python cli.py --mcq or python cli.py --coding)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['--mcq', '-m', 'mcq']:
            solve("mcq")
            return
        elif arg in ['--coding', '-c', 'coding', 'code']:
            solve("coding")
            return
        elif arg in ['--sql', '--fullstack', '-s']:
            solve("fullstack")
            return
        elif arg in ['--game', '-p']:
            solve("game")
            return

    interactive_loop()


if __name__ == '__main__':
    main()
