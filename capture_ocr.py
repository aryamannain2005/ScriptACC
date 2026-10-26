#!/usr/bin/env python3
"""
ScriptACC – HostLab macOS Client
=================================
Full hotkey-driven screen capture → OCR → LLM → overlay + auto-type.

Hotkeys (Option = Alt on macOS):
  Option+M / Ctrl+Alt+M  → MCQ Solver
  Option+8 / Ctrl+Alt+8  → Coding / DSA Solver
  Option+9 / Ctrl+Alt+9  → FullStack / SQL / Web / Debug
  Option+0 / Ctrl+Alt+0  → Game & Puzzle Solver
  Option+B / Ctrl+Alt+B  → Add screenshot to buffer (multi-screenshot)
  Option+F / Ctrl+Alt+F  → Auto-Type last solution
  Option+G / Ctrl+Alt+G  → Ghost-Type (stealth, humanized delays)
  Option+R / Ctrl+Alt+R  → Pause / Resume typing
  Option+E / Ctrl+Alt+E  → Stop typing immediately
  Option+D / Ctrl+Alt+D  → Show / Hide overlay
  Option+N / Ctrl+Alt+N  → Dim overlay (9% stealth)
  Option+I / Ctrl+Alt+I  → Show hotkey guide
  Option+Shift+X         → Emergency exit

Terminal Commands (Fallback without Accessibility permissions):
  m, 8, 9, 0, b, f, g, r, e, d, n, i, q  (or ENTER = coding mode)
"""

import os
import sys
import time
import random
import yaml
import httpx
import pytesseract
from PIL import Image
import pyautogui
import threading

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot
from PySide6.QtGui import QCursor

# Optimize pyautogui speed
pyautogui.PAUSE = 0.001

# ── Load configuration ────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
with open(CONFIG_PATH, 'r') as f:
    cfg = yaml.safe_load(f)

SERVER_URL = cfg.get('server_url', 'http://127.0.0.1:8000/process')
TOKEN = cfg.get('token', '')
OCR_LANG = cfg.get('ocr_language', 'eng')


# ── Global application state ─────────────────────────────────────────────────
class AppState:
    last_answer = ""
    screenshot_buffer = []       # list of PIL Images for multi-SS mode
    typing_active = False
    typing_paused = False
    typing_stop = False
    overlay_visible = True
    overlay_dimmed = False

state = AppState()


# ── Thread-safe Qt signal bridge ─────────────────────────────────────────────
class Communicator(QObject):
    overlay_requested = Signal(str, float)   # message, opacity
    overlay_hide = Signal()
    overlay_dim = Signal()
    app_quit = Signal()


# ── Core Capture & OCR functions ─────────────────────────────────────────────

def capture_screen() -> Image.Image:
    print("  📸 Capturing screen...")
    return pyautogui.screenshot()


def ocr_image(img: Image.Image) -> str:
    print("  🔍 Running OCR...")
    try:
        text = pytesseract.image_to_string(img, lang=OCR_LANG)
        return text.strip()
    except Exception as e:
        print(f"  ❌ OCR error: {e}")
        return ""


def ocr_multiple_images(images: list) -> str:
    """OCR multiple buffered screenshots and combine text."""
    all_text = []
    for i, img in enumerate(images):
        print(f"  🔍 OCR on buffer image {i+1}/{len(images)}...")
        try:
            text = pytesseract.image_to_string(img, lang=OCR_LANG)
            if text.strip():
                all_text.append(text.strip())
        except Exception as e:
            print(f"  ⚠️ OCR buffer error: {e}")
    return "\n\n---\n\n".join(all_text)


def send_to_server(prompt: str, mode: str = "general") -> dict:
    print(f"  📡 Sending to server (mode: {mode})...")
    payload = {'token': TOKEN, 'prompt': prompt, 'mode': mode}
    try:
        resp = httpx.post(SERVER_URL, json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        return {'error': 'Cannot connect to server. Is uvicorn running on port 8000?'}
    except httpx.TimeoutException:
        return {'error': 'Server timed out (model may be loading).'}
    except Exception as e:
        return {'error': str(e)}


# ── Auto-type / Ghost-type ───────────────────────────────────────────────────

def auto_type(text: str, ghost: bool = False):
    """Type out text character by character. Ghost mode = slower + random human delays."""
    state.typing_active = True
    state.typing_paused = False
    state.typing_stop = False

    print(f"  ⏳ {'Ghost' if ghost else 'Auto'}-typing in 2s... Focus your editor window!")
    for _ in range(20):
        if state.typing_stop:
            print("  ⏹ Typing cancelled.")
            state.typing_active = False
            return
        time.sleep(0.1)

    delay = 0.07 if ghost else 0.015
    print(f"  ⌨️  {'Ghost' if ghost else 'Auto'}-typing {len(text)} chars...")

    for char in text:
        if state.typing_stop:
            print("  ⏹  Typing stopped.")
            break
        while state.typing_paused:
            time.sleep(0.1)
            if state.typing_stop:
                break

        try:
            if char == '\n':
                pyautogui.press('return')
            elif char == '\t':
                pyautogui.press('tab')
            else:
                pyautogui.write(char)
        except Exception:
            pass

        sleep_time = delay + (random.uniform(0.02, 0.12) if ghost else 0)
        time.sleep(sleep_time)

    state.typing_active = False
    print("  ✅ Typing complete.")


# ── Anti-Capture / Screen Share Stealth Engine ──────────────────────────────

def apply_screen_share_protection(widget):
    """
    Excludes the overlay window from screen-sharing, recording, and proctoring capture streams.
    - Windows: Uses SetWindowDisplayAffinity (WDA_EXCLUDEFROMCAPTURE) -> 100% invisible in Zoom/Teams/Meet
    - macOS: Uses NSWindowSharingNone (0) -> invisible to ScreenCaptureKit / Window sharing
    """
    # Windows native DWM exclusion
    if sys.platform == 'win32':
        try:
            import ctypes
            hwnd = int(widget.winId())
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Windows 10 2004+ and Windows 11)
            result = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            if not result:
                # Fallback for Windows 7/8/10 older
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000001)
        except Exception:
            pass

    # macOS native Cocoa exclusion
    elif sys.platform == 'darwin':
        try:
            import ctypes
            import ctypes.util
            objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]

            msgSend = objc.objc_msgSend
            msgSend.restype = ctypes.c_void_p
            msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

            sel_window = objc.sel_registerName(b"window")
            sel_setSharingType = objc.sel_registerName(b"setSharingType:")

            view_ptr = int(widget.winId())
            win_ptr = msgSend(view_ptr, sel_window)
            if win_ptr:
                msgSend_set = objc.objc_msgSend
                msgSend_set.restype = None
                msgSend_set.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                msgSend_set(win_ptr, sel_setSharingType, 0)  # 0 = NSWindowSharingNone
        except Exception:
            pass


# ── Overlay UI Widget ────────────────────────────────────────────────────────

class OverlayLabel(QLabel):
    def __init__(self, message: str, opacity: float = 0.92):
        super().__init__(message)
        self.setWordWrap(True)
        self.setMaximumWidth(700)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(opacity)

        self.setStyleSheet(
            "background-color: rgba(18, 18, 22, 235);"
            "color: #00FF66;"
            "padding: 16px 20px;"
            "border-radius: 12px;"
            "font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;"
            "font-size: 12pt;"
            "font-weight: 500;"
            "border: 1px solid rgba(0, 255, 102, 0.35);"
        )
        self.adjustSize()

        # Clamp safely within visible screen boundaries
        cursor_pos = QCursor.pos()
        screen = QApplication.primaryScreen().availableGeometry()
        x = min(cursor_pos.x() + 25, screen.width() - self.width() - 30)
        y = min(cursor_pos.y() + 25, screen.height() - self.height() - 30)
        self.move(max(30, x), max(30, y))

        # Apply stealth protection: Inaudible / Invisible to Screen Sharing & Recorders
        apply_screen_share_protection(self)

        # Auto-dismiss after 25 seconds
        QTimer.singleShot(25000, self.close)

    def mousePressEvent(self, event):
        self.close()


# ── Main Thread Overlay Manager (QObject) ────────────────────────────────────

class OverlayManager(QObject):
    def __init__(self):
        super().__init__()
        self.current_overlay = None
        self.overlays = []

    @Slot(str, float)
    def show_overlay(self, message: str, opacity: float):
        if self.current_overlay:
            try:
                self.current_overlay.close()
            except Exception:
                pass

        if not state.overlay_visible:
            return

        o = OverlayLabel(message, opacity)
        self.overlays.append(o)
        self.current_overlay = o
        o.show()
        o.raise_()
        o.activateWindow()
        QTimer.singleShot(26000, lambda: self.overlays.remove(o) if o in self.overlays else None)

    @Slot()
    def hide_overlay(self):
        if self.current_overlay:
            try:
                self.current_overlay.close()
            except Exception:
                pass

    @Slot()
    def dim_overlay(self):
        state.overlay_dimmed = not state.overlay_dimmed
        opacity = 0.09 if state.overlay_dimmed else 0.92
        if self.current_overlay:
            try:
                self.current_overlay.setWindowOpacity(opacity)
            except Exception:
                pass
        elif state.last_answer:
            self.show_overlay(state.last_answer, opacity)

    @Slot()
    def quit_app(self):
        QApplication.instance().quit()


# ── Main Application ─────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    comm = Communicator()
    mgr = OverlayManager()

    # Crucial: QueuedConnection ensures slot execution ALWAYS occurs on the Main GUI Thread
    comm.overlay_requested.connect(mgr.show_overlay, Qt.QueuedConnection)
    comm.overlay_hide.connect(mgr.hide_overlay, Qt.QueuedConnection)
    comm.overlay_dim.connect(mgr.dim_overlay, Qt.QueuedConnection)
    comm.app_quit.connect(mgr.quit_app, Qt.QueuedConnection)

    # ── Capture + solve worker ────────────────────────────────────────────
    def process_mode(mode: str):
        if state.screenshot_buffer:
            print(f"\n🔥 Processing {len(state.screenshot_buffer)} buffered screenshots (mode: {mode})")
            text = ocr_multiple_images(state.screenshot_buffer)
            state.screenshot_buffer.clear()
        else:
            print(f"\n🔥 Screen capture triggered (mode: {mode})")
            img = capture_screen()
            text = ocr_image(img)

        if not text:
            print("  ⚠️ No text detected on screen.")
            comm.overlay_requested.emit("⚠️ No text detected on screen.", 0.92)
            return

        print(f"  📝 {len(text)} characters extracted")
        response = send_to_server(text, mode)

        if 'error' in response:
            answer = f"❌ {response['error']}"
        else:
            answer = response.get('answer', 'No answer received.')

        state.last_answer = answer
        print(f"\n  ✅ Answer ({mode}):\n{'─' * 55}")
        print(answer)
        print('─' * 55)

        opacity = 0.09 if state.overlay_dimmed else 0.92
        comm.overlay_requested.emit(answer, opacity)

    # ── Action dispatchers ────────────────────────────────────────────────
    def on_mcq():
        threading.Thread(target=process_mode, args=("mcq",), daemon=True).start()

    def on_coding():
        threading.Thread(target=process_mode, args=("coding",), daemon=True).start()

    def on_fullstack():
        threading.Thread(target=process_mode, args=("fullstack",), daemon=True).start()

    def on_game():
        threading.Thread(target=process_mode, args=("game",), daemon=True).start()

    def on_buffer():
        img = capture_screen()
        state.screenshot_buffer.append(img)
        n = len(state.screenshot_buffer)
        print(f"  📋 Screenshot added to buffer ({n} total)")
        comm.overlay_requested.emit(f"📋 Buffer: {n} screenshot(s)\nPress Option+M/8/9/0 to solve", 0.92)

    def on_auto_type():
        if state.last_answer:
            threading.Thread(target=auto_type, args=(state.last_answer, False), daemon=True).start()
        else:
            print("  ⚠️  No answer to type. Capture first.")

    def on_ghost_type():
        if state.last_answer:
            threading.Thread(target=auto_type, args=(state.last_answer, True), daemon=True).start()
        else:
            print("  ⚠️  No answer to type. Capture first.")

    def on_pause_resume():
        if state.typing_active:
            state.typing_paused = not state.typing_paused
            status = "⏸ PAUSED" if state.typing_paused else "▶️ RESUMED"
            print(f"  {status}")
            comm.overlay_requested.emit(status, 0.92)

    def on_stop_typing():
        state.typing_stop = True
        print("  ⏹ Stop signal sent.")

    def on_toggle_overlay():
        state.overlay_visible = not state.overlay_visible
        if not state.overlay_visible:
            comm.overlay_hide.emit()
            print("  👁  Overlay HIDDEN")
        else:
            print("  👁  Overlay VISIBLE")
            if state.last_answer:
                comm.overlay_requested.emit(state.last_answer, 0.92)

    def on_dim():
        comm.overlay_dim.emit()
        print(f"  🔅 Overlay {'dimmed (9%)' if state.overlay_dimmed else 'restored'}")

    def on_guide():
        guide = (
            "🎹 HostLab / ScriptACC Hotkeys:\n"
            "─────────────────────────────\n"
            "⌥+M / ⌃⌥M  : Multi-MCQ Solver\n"
            "⌥+8 / ⌃⌥8  : Coding / DSA Solver\n"
            "⌥+9 / ⌃⌥9  : FullStack / SQL / Debug\n"
            "⌥+0 / ⌃⌥0  : Game & Puzzle Solver\n"
            "⌥+B / ⌃⌥B  : Add SS to Buffer\n"
            "⌥+F / ⌃⌥F  : Auto-Type Solution\n"
            "⌥+G / ⌃⌥G  : Ghost-Type (Stealth)\n"
            "⌥+R / ⌃⌥R  : Pause / Resume Typing\n"
            "⌥+E / ⌃⌥E  : Stop Typing\n"
            "⌥+D / ⌃⌥D  : Show / Hide Overlay\n"
            "⌥+N / ⌃⌥N  : Dim 9% (Stealth)\n"
            "⌥+I / ⌃⌥I  : Show Hotkey Guide\n"
            "⌥+⇧+X      : EMERGENCY EXIT"
        )
        comm.overlay_requested.emit(guide, 0.92)

    def on_exit():
        print("\n🚪 Emergency exit requested!")
        state.typing_stop = True
        comm.app_quit.emit()

    # ── Register pynput global hotkeys ───────────────────────────────────
    def start_hotkey_listener():
        try:
            from pynput import keyboard as pkb

            hotkeys = {
                # MCQ Solver
                '<alt>+m': on_mcq,
                '<ctrl>+<alt>+m': on_mcq,
                '<cmd>+<alt>+m': on_mcq,
                '<alt>+µ': on_mcq,
                # Coding / DSA Solver
                '<alt>+8': on_coding,
                '<ctrl>+<alt>+8': on_coding,
                '<cmd>+<alt>+8': on_coding,
                '<alt>+•': on_coding,
                # FullStack / SQL / Web
                '<alt>+9': on_fullstack,
                '<ctrl>+<alt>+9': on_fullstack,
                '<cmd>+<alt>+9': on_fullstack,
                '<alt>+ª': on_fullstack,
                # Game & Puzzle Solver
                '<alt>+0': on_game,
                '<ctrl>+<alt>+0': on_game,
                '<cmd>+<alt>+0': on_game,
                '<alt>+º': on_game,
                # Multi-Screenshot Buffer
                '<alt>+b': on_buffer,
                '<ctrl>+<alt>+b': on_buffer,
                '<cmd>+<alt>+b': on_buffer,
                '<alt>+∫': on_buffer,
                # Auto-Type
                '<alt>+f': on_auto_type,
                '<ctrl>+<alt>+f': on_auto_type,
                '<cmd>+<alt>+f': on_auto_type,
                '<alt>+ƒ': on_auto_type,
                # Ghost-Type (Stealth)
                '<alt>+g': on_ghost_type,
                '<ctrl>+<alt>+g': on_ghost_type,
                '<cmd>+<alt>+g': on_ghost_type,
                '<alt>+©': on_ghost_type,
                # Pause / Resume
                '<alt>+r': on_pause_resume,
                '<ctrl>+<alt>+r': on_pause_resume,
                '<cmd>+<alt>+r': on_pause_resume,
                '<alt>+®': on_pause_resume,
                # Stop Typing
                '<alt>+e': on_stop_typing,
                '<ctrl>+<alt>+e': on_stop_typing,
                '<cmd>+<alt>+e': on_stop_typing,
                '<alt>+´': on_stop_typing,
                # Hide / Show Overlay
                '<alt>+d': on_toggle_overlay,
                '<ctrl>+<alt>+d': on_toggle_overlay,
                '<cmd>+<alt>+d': on_toggle_overlay,
                '<alt>+∂': on_toggle_overlay,
                # Dim 9% (Stealth)
                '<alt>+n': on_dim,
                '<ctrl>+<alt>+n': on_dim,
                '<cmd>+<alt>+n': on_dim,
                '<alt>+~': on_dim,
                # Guide HUD
                '<alt>+i': on_guide,
                '<ctrl>+<alt>+i': on_guide,
                '<cmd>+<alt>+i': on_guide,
                '<alt>+ˆ': on_guide,
                # Emergency Exit
                '<alt>+<shift>+x': on_exit,
                '<ctrl>+<alt>+x': on_exit,
                '<cmd>+<alt>+x': on_exit,
            }

            listener = pkb.GlobalHotKeys(hotkeys)
            listener.daemon = True
            listener.start()
            print("  ✅ Global hotkey listeners active")
            return True
        except Exception as e:
            print(f"  ⚠️  Global hotkey listener warning: {e}")
            print("  ℹ️  If hotkeys do not respond, grant Accessibility permission in macOS Settings.")
            return False

    hotkey_ok = start_hotkey_listener()

    # ── Terminal interactive command loop (Zero-Permission Fallback) ──────
    def input_loop():
        time.sleep(0.5)
        while True:
            try:
                cmd = input("\n⏎ Command [m/8/9/0/b/f/g/r/e/d/n/i/q] (ENTER=Coding): ").strip().lower()
                if cmd == 'q':
                    comm.app_quit.emit()
                    break
                elif cmd == 'm':
                    on_mcq()
                elif cmd == '8' or cmd == '':
                    on_coding()
                elif cmd == '9':
                    on_fullstack()
                elif cmd == '0':
                    on_game()
                elif cmd == 'b':
                    on_buffer()
                elif cmd == 'f':
                    on_auto_type()
                elif cmd == 'g':
                    on_ghost_type()
                elif cmd == 'r':
                    on_pause_resume()
                elif cmd == 'e':
                    on_stop_typing()
                elif cmd == 'd':
                    on_toggle_overlay()
                elif cmd == 'n':
                    on_dim()
                elif cmd == 'i':
                    on_guide()
                else:
                    print("  Unknown command. Available: m/8/9/0/b/f/g/r/e/d/n/i/q (ENTER=Coding)")
            except (KeyboardInterrupt, EOFError):
                comm.app_quit.emit()
                break

    input_thread = threading.Thread(target=input_loop, daemon=True)
    input_thread.start()

    # ── Startup Banner ───────────────────────────────────────────────────
    print("=" * 60)
    print("       ScriptACC – HostLab macOS Client Ready")
    print("=" * 60)
    print(f"  Server   : {SERVER_URL}")
    print(f"  Model    : {cfg.get('ollama_model', 'llama3.2:3b')}")
    print(f"  OCR Lang : {OCR_LANG}")
    print("─" * 60)
    print("  HOTKEYS (Option + Key, or Ctrl + Alt + Key):")
    print("    Option + M  : Multi-MCQ Solver")
    print("    Option + 8  : Coding / DSA Solver")
    print("    Option + 9  : FullStack / SQL / Web / Debug")
    print("    Option + 0  : Game & Puzzle Solver")
    print("    Option + B  : Add Screenshot to Buffer")
    print("    Option + F  : Auto-Type Solution")
    print("    Option + G  : Ghost-Type (Stealth)")
    print("    Option + R  : Pause / Resume Typing")
    print("    Option + E  : Stop Typing")
    print("    Option + D  : Show / Hide Overlay UI")
    print("    Option + N  : Dim 9% (Stealth)")
    print("    Option + I  : Show Hotkey Guide")
    print("    Option+Shift+X : Emergency Exit")
    print("─" * 60)
    print("  TERMINAL FALLBACK (Zero permission needed):")
    print("    Press ENTER for Coding Mode, or type m, 8, 9, 0, b, f, g, q")
    print("=" * 60)

    # Instant Welcome Popup on Screen
    QTimer.singleShot(600, lambda: comm.overlay_requested.emit(
        "🟢 ScriptACC Connected!\n─────────────────────────────\nModel: Groq 120B Active ⚡\n⌥+8 (Coding) | ⌥+M (MCQ)\nOr press ENTER in terminal!", 0.95
    ))

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
