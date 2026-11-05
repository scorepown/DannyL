"""
Game recorder: collects training data for the screen-reading bot.

While recording it saves screenshots of ONE chosen window and logs the game
keys you press. Nothing is captured while another window is in front, and only
the keys in GAME_KEYS are logged, so typing elsewhere is never recorded.

Turn it on/off with the Start/Stop button or F9 from any window. Recording
stops by itself after MAX_MINUTES. Each session is saved to
recordings/<date_time>/ and packed into recordings/<date_time>.zip.

Session contents:
  frames/000001.jpg   screenshots of the window's client area
  frames.csv          frame, time, left, top, width, height
  keys.csv            time, key, action (down/up)
  meta.json           window title, screen size, fps, totals

Install:  pip install pynput mss pillow
Run:      pythonw game_recorder.py   (or double-click game_recorder.bat)
"""
import csv
import ctypes
import json
import threading
import time
import tkinter as tk
import zipfile
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from tkinter import ttk

import mss
from PIL import Image
from pynput import keyboard

TOGGLE_KEY = keyboard.Key.f9
FPS = 2
JPEG_QUALITY = 80
MAX_MINUTES = 15
RECORDINGS_DIR = Path(__file__).resolve().parent / "recordings"

GAME_KEYS = {
    keyboard.Key.ctrl: "ctrl",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.space: "space",
    keyboard.Key.up: "up",
    keyboard.Key.down: "down",
    keyboard.Key.left: "left",
    keyboard.Key.right: "right",
}
VK_W = 0x57  # Matched by key position, so it also works on a Hebrew layout.

user32 = ctypes.windll.user32


def enable_dpi_awareness():
    """Report real pixels, so window rectangles match what mss captures."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        user32.SetProcessDPIAware()


def window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def list_windows():
    """Return {title: hwnd} for visible top-level windows that have a title."""
    windows = {}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = window_title(hwnd)
            if title:
                windows[title] = hwnd
        return True

    user32.EnumWindows(callback_type(collect), 0)
    return windows


def client_rect(hwnd):
    """Return the window's inner area as an mss region, or None if unusable."""
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    if rect.right <= 0 or rect.bottom <= 0:
        return None
    return {"left": origin.x, "top": origin.y, "width": rect.right, "height": rect.bottom}


def game_key_name(key):
    if key in GAME_KEYS:
        return GAME_KEYS[key]
    if getattr(key, "vk", None) == VK_W:
        return "w"
    return None


class Recorder:
    def __init__(self, require_foreground=True):
        self.require_foreground = require_foreground
        self.stop_event = threading.Event()
        self.thread = None
        self.status = "Stopped"
        self.hwnd = None
        self.session_dir = None
        self.started_at = 0.0
        self.frames = 0
        self.keys = 0
        self.key_rows = []
        self.keys_down = set()
        self.key_lock = threading.Lock()

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, hwnd):
        if self.running:
            return
        self.hwnd = hwnd
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def wait(self, timeout=None):
        if self.thread is not None:
            self.thread.join(timeout)

    def game_in_front(self):
        return not self.require_foreground or user32.GetForegroundWindow() == self.hwnd

    def log_key(self, key, action):
        if not self.running or self.stop_event.is_set():
            return
        name = game_key_name(key)
        if name is None or not self.game_in_front():
            return
        with self.key_lock:
            # Windows repeats "down" while a key is held; keep only the first.
            if action == "down" and name in self.keys_down:
                return
            if action == "down":
                self.keys_down.add(name)
            else:
                self.keys_down.discard(name)
            self.key_rows.append((round(time.time() - self.started_at, 3), name, action))
            self.keys += 1

    def _run(self):
        try:
            self._record()
        except Exception as error:  # Shown in the window: pythonw has no console.
            self.status = f"Error: {error}"
            raise

    def _record(self):
        title = window_title(self.hwnd)
        self.session_dir = RECORDINGS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        frames_dir = self.session_dir / "frames"
        frames_dir.mkdir(parents=True)
        self.started_at = time.time()
        self.frames = 0
        self.keys = 0
        self.key_rows = []
        self.keys_down = set()
        deadline = self.started_at + MAX_MINUTES * 60

        with mss.mss() as screen, open(self.session_dir / "frames.csv", "w", newline="") as frames_file:
            frames_csv = csv.writer(frames_file)
            frames_csv.writerow(["frame", "time", "left", "top", "width", "height"])
            while not self.stop_event.is_set() and time.time() < deadline:
                tick = time.time()
                region = client_rect(self.hwnd)
                if region is None:
                    self.status = "Paused - window not available"
                elif not self.game_in_front():
                    self.status = "Paused - game window is not in front"
                else:
                    shot = screen.grab(region)
                    image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    self.frames += 1
                    image.save(frames_dir / f"{self.frames:06d}.jpg", quality=JPEG_QUALITY)
                    frames_csv.writerow([self.frames, round(tick - self.started_at, 3), region["left"],
                                         region["top"], region["width"], region["height"]])
                    self.status = f"Recording - {self.frames} frames, {self.keys} keys"
                self.stop_event.wait(max(0.0, 1 / FPS - (time.time() - tick)))
            monitor = screen.monitors[0]

        self.stop_event.set()
        self.status = "Saving..."
        self._save(title, monitor)

    def _save(self, title, monitor):
        with self.key_lock, open(self.session_dir / "keys.csv", "w", newline="") as keys_file:
            keys_csv = csv.writer(keys_file)
            keys_csv.writerow(["time", "key", "action"])
            keys_csv.writerows(self.key_rows)
        meta = {
            "window_title": title,
            "screen_width": monitor["width"],
            "screen_height": monitor["height"],
            "fps": FPS,
            "frames": self.frames,
            "keys": self.keys,
            "seconds": round(time.time() - self.started_at, 1),
        }
        (self.session_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        zip_path = self.session_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as archive:
            for path in sorted(self.session_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(self.session_dir.parent))
        size_mb = zip_path.stat().st_size / 1_000_000
        self.status = f"Saved {zip_path.name} ({size_mb:.0f} MB, {self.frames} frames)"


class App:
    def __init__(self, root, recorder):
        self.root = root
        self.recorder = recorder
        self.hotkey_pressed = threading.Event()
        self.windows = {}

        root.title("Game Recorder")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status_label = tk.Label(root, text="", width=44, wraplength=340, font=("Segoe UI", 10, "bold"))
        self.status_label.pack(padx=12, pady=(12, 6))

        tk.Label(root, text="Game window:").pack()
        row = tk.Frame(root)
        row.pack(padx=12, pady=4)
        self.window_var = tk.StringVar()
        self.window_box = ttk.Combobox(row, textvariable=self.window_var, width=38, state="readonly")
        self.window_box.pack(side=tk.LEFT)
        tk.Button(row, text="Refresh", command=self.refresh_windows).pack(side=tk.LEFT, padx=4)

        self.button = tk.Button(root, text="Start", width=14, font=("Segoe UI", 11), command=self.toggle)
        self.button.pack(pady=6)

        tk.Label(root, text=f"F9 = start / stop from any window. Stops by itself after {MAX_MINUTES} minutes.",
                 fg="gray").pack(pady=(0, 12))

        self.refresh_windows()
        self.refresh()

    def load_windows(self):
        self.windows = {title: hwnd for title, hwnd in list_windows().items() if title != self.root.title()}

    def refresh_windows(self):
        self.load_windows()
        titles = sorted(self.windows)
        self.window_box["values"] = titles
        if self.window_var.get() not in self.windows:
            maple = [title for title in titles if "maple" in title.lower()]
            self.window_var.set(maple[0] if maple else "")

    def toggle(self):
        if self.recorder.running:
            self.recorder.stop()
            return
        self.load_windows()
        hwnd = self.windows.get(self.window_var.get())
        if hwnd is None:
            self.recorder.status = "Choose the game window first"
            return
        self.recorder.start(hwnd)

    def refresh(self):
        if self.hotkey_pressed.is_set():
            self.hotkey_pressed.clear()
            self.toggle()
        running = self.recorder.running
        self.status_label.config(text=self.recorder.status, fg="green" if running else "black")
        self.button.config(text="Stop" if running else "Start")
        self.root.after(200, self.refresh)

    def on_close(self):
        self.recorder.stop()
        self.recorder.wait(30)
        self.root.destroy()


def main():
    enable_dpi_awareness()
    recorder = Recorder()
    root = tk.Tk()
    app = App(root, recorder)

    def on_press(key):
        if key == TOGGLE_KEY:
            # The Tk thread owns the widgets; refresh() picks this up.
            app.hotkey_pressed.set()
        else:
            recorder.log_key(key, "down")

    def on_release(key):
        recorder.log_key(key, "up")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    try:
        root.mainloop()
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
