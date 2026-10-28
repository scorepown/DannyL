"""
Presses Ctrl once at startup, then every 10 seconds presses an arrow key,
alternating left and right.

Install:  pip install pynput
Run:      python keyboard_mover.py
Stop:     Ctrl+C in the terminal
"""
import time

from pynput.keyboard import Controller, Key

INTERVAL_SECONDS = 10

keyboard = Controller()


def tap(key):
    keyboard.press(key)
    time.sleep(0.05)
    keyboard.release(key)


def main():
    print("Starting in 3 seconds... switch to the target window.")
    time.sleep(3)

    tap(Key.ctrl)
    print("Pressed Ctrl")

    direction = Key.left
    try:
        while True:
            time.sleep(INTERVAL_SECONDS)
            tap(direction)
            print("Pressed", "Left" if direction == Key.left else "Right")
            direction = Key.right if direction == Key.left else Key.left
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
