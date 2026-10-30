"""
Keyboard bot with an on/off switch.

While running it holds Ctrl down and every N seconds presses an arrow key,
alternating left and right (Ctrl+Left / Ctrl+Right).

Turn it on/off:
  - F8 anywhere (starts immediately, in whatever window is focused), or
  - the Start/Stop button (starts after a 3 second countdown, so you can
    switch to the target window).
Closing the window stops the bot and releases Ctrl.

Install:  pip install pynput
Run:      pythonw keyboard_bot.py   (or double-click keyboard_bot.bat)
"""
import threading
import time
import tkinter as tk

from pynput import keyboard

TOGGLE_KEY = keyboard.Key.f8
DEFAULT_INTERVAL = 10
COUNTDOWN_SECONDS = 3


class Bot:
    def __init__(self):
        self.controller = keyboard.Controller()
        self.stop_event = threading.Event()
        self.thread = None
        self.status = "Stopped"
        self.interval = DEFAULT_INTERVAL

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, countdown=0):
        if self.running:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(countdown,), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
        self.status = "Stopped"

    def toggle(self, countdown=0):
        if self.running:
            self.stop()
        else:
            self.start(countdown)

    def _tap(self, key):
        self.controller.press(key)
        time.sleep(0.05)
        self.controller.release(key)

    def _run(self, countdown):
        for remaining in range(countdown, 0, -1):
            self.status = f"Starting in {remaining}..."
            if self.stop_event.wait(1):
                return

        self.controller.press(keyboard.Key.ctrl)
        direction = keyboard.Key.left
        try:
            self.status = "Running - holding Ctrl"
            while not self.stop_event.wait(self.interval):
                self._tap(direction)
                name = "Left" if direction == keyboard.Key.left else "Right"
                self.status = f"Running - pressed Ctrl+{name}"
                direction = keyboard.Key.right if direction == keyboard.Key.left else keyboard.Key.left
        finally:
            self.controller.release(keyboard.Key.ctrl)


class App:
    def __init__(self, root, bot):
        self.root = root
        self.bot = bot
        self.hotkey_pressed = threading.Event()

        root.title("Keyboard Bot")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status_label = tk.Label(root, text="", width=32, font=("Segoe UI", 11, "bold"))
        self.status_label.pack(padx=12, pady=(12, 6))

        interval_row = tk.Frame(root)
        interval_row.pack(pady=4)
        tk.Label(interval_row, text="Interval (seconds):").pack(side=tk.LEFT)
        self.interval_var = tk.IntVar(value=DEFAULT_INTERVAL)
        tk.Spinbox(interval_row, from_=1, to=3600, width=6, textvariable=self.interval_var).pack(side=tk.LEFT, padx=4)

        self.button = tk.Button(root, text="Start", width=14, font=("Segoe UI", 11), command=self.on_button)
        self.button.pack(pady=6)

        tk.Label(root, text="F8 = start / stop from any window", fg="gray").pack(pady=(0, 12))

        self.refresh()

    def read_interval(self):
        try:
            self.bot.interval = max(1, int(self.interval_var.get()))
        except (tk.TclError, ValueError):
            self.bot.interval = DEFAULT_INTERVAL

    def on_button(self):
        self.read_interval()
        self.bot.toggle(countdown=COUNTDOWN_SECONDS)

    def on_hotkey(self):
        self.read_interval()
        self.bot.toggle(countdown=0)

    def refresh(self):
        if self.hotkey_pressed.is_set():
            self.hotkey_pressed.clear()
            self.on_hotkey()
        running = self.bot.running
        self.status_label.config(text=self.bot.status if running else "Stopped",
                                 fg="green" if running else "red")
        self.button.config(text="Stop" if running else "Start")
        self.root.after(200, self.refresh)

    def on_close(self):
        self.bot.stop()
        self.root.destroy()


def main():
    bot = Bot()
    root = tk.Tk()
    app = App(root, bot)

    def on_press(key):
        if key == TOGGLE_KEY:
            # The Tk thread owns the widgets; refresh() picks this up.
            app.hotkey_pressed.set()

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    try:
        root.mainloop()
    finally:
        listener.stop()
        bot.stop()


if __name__ == "__main__":
    main()
