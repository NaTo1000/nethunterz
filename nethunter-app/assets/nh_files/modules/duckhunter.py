#!/usr/bin/env python3
"""
duckhunter.py – NetHunter DuckScript interpreter and HID injector.

Parses Hak5 DuckScript syntax and injects keystrokes via the
USB HID gadget interface.

Supported commands:
    REM           Comment (ignored)
    DELAY <ms>    Pause execution for <ms> milliseconds
    STRING <text> Type a string
    ENTER         Press Enter
    GUI [key]     Press Windows/Meta key (optionally with another key)
    CTRL [key]    Press Ctrl (optionally with another key)
    ALT [key]     Press Alt (optionally with another key)
    SHIFT [key]   Press Shift (optionally with another key)
    TAB           Press Tab
    CAPSLOCK      Press Caps Lock
    BACKSPACE     Press Backspace
    DELETE        Press Delete
    UPARROW       Press Up Arrow
    DOWNARROW     Press Down Arrow
    LEFTARROW     Press Left Arrow
    RIGHTARROW    Press Right Arrow
    ESCAPE        Press Escape

Usage:
    python3 duckhunter.py -d /dev/hidg0 -f payload.txt
"""

import argparse
import sys
import time

# HID modifier constants
MOD_LCTRL  = 0x01
MOD_LSHIFT = 0x02
MOD_LALT   = 0x04
MOD_LMETA  = 0x08

# Special key codes
KEY_ENTER      = 0x28
KEY_BACKSPACE  = 0x2A
KEY_TAB        = 0x2B
KEY_CAPSLOCK   = 0x39
KEY_DELETE     = 0x4C
KEY_RIGHT      = 0x4F
KEY_LEFT       = 0x50
KEY_DOWN       = 0x51
KEY_UP         = 0x52
KEY_ESCAPE     = 0x29

# Single-key name → keycode map for modifier combos
_KEY_NAMES = {
    'ENTER': KEY_ENTER, 'BACKSPACE': KEY_BACKSPACE, 'TAB': KEY_TAB,
    'DELETE': KEY_DELETE, 'ESCAPE': KEY_ESCAPE,
    'UPARROW': KEY_UP, 'DOWNARROW': KEY_DOWN,
    'LEFTARROW': KEY_LEFT, 'RIGHTARROW': KEY_RIGHT,
    'A': 0x04, 'B': 0x05, 'C': 0x06, 'D': 0x07, 'E': 0x08,
    'F': 0x09, 'G': 0x0A, 'H': 0x0B, 'I': 0x0C, 'J': 0x0D,
    'K': 0x0E, 'L': 0x0F, 'M': 0x10, 'N': 0x11, 'O': 0x12,
    'P': 0x13, 'Q': 0x14, 'R': 0x15, 'S': 0x16, 'T': 0x17,
    'U': 0x18, 'V': 0x19, 'W': 0x1A, 'X': 0x1B, 'Y': 0x1C,
    'Z': 0x1D, 'F1': 0x3A, 'F2': 0x3B, 'F3': 0x3C, 'F4': 0x3D,
    'F5': 0x3E, 'F6': 0x3F, 'F7': 0x40, 'F8': 0x41, 'F9': 0x42,
    'F10': 0x43, 'F11': 0x44, 'F12': 0x45,
    'SPACE': 0x2C,
}

_CHAR_KEYMAP = {
    'a': (0x00, 0x04), 'b': (0x00, 0x05), 'c': (0x00, 0x06),
    'd': (0x00, 0x07), 'e': (0x00, 0x08), 'f': (0x00, 0x09),
    'g': (0x00, 0x0A), 'h': (0x00, 0x0B), 'i': (0x00, 0x0C),
    'j': (0x00, 0x0D), 'k': (0x00, 0x0E), 'l': (0x00, 0x0F),
    'm': (0x00, 0x10), 'n': (0x00, 0x11), 'o': (0x00, 0x12),
    'p': (0x00, 0x13), 'q': (0x00, 0x14), 'r': (0x00, 0x15),
    's': (0x00, 0x16), 't': (0x00, 0x17), 'u': (0x00, 0x18),
    'v': (0x00, 0x19), 'w': (0x00, 0x1A), 'x': (0x00, 0x1B),
    'y': (0x00, 0x1C), 'z': (0x00, 0x1D),
    'A': (MOD_LSHIFT, 0x04), 'B': (MOD_LSHIFT, 0x05),
    'C': (MOD_LSHIFT, 0x06), 'D': (MOD_LSHIFT, 0x07),
    'E': (MOD_LSHIFT, 0x08), 'F': (MOD_LSHIFT, 0x09),
    'G': (MOD_LSHIFT, 0x0A), 'H': (MOD_LSHIFT, 0x0B),
    'I': (MOD_LSHIFT, 0x0C), 'J': (MOD_LSHIFT, 0x0D),
    'K': (MOD_LSHIFT, 0x0E), 'L': (MOD_LSHIFT, 0x0F),
    'M': (MOD_LSHIFT, 0x10), 'N': (MOD_LSHIFT, 0x11),
    'O': (MOD_LSHIFT, 0x12), 'P': (MOD_LSHIFT, 0x13),
    'Q': (MOD_LSHIFT, 0x14), 'R': (MOD_LSHIFT, 0x15),
    'S': (MOD_LSHIFT, 0x16), 'T': (MOD_LSHIFT, 0x17),
    'U': (MOD_LSHIFT, 0x18), 'V': (MOD_LSHIFT, 0x19),
    'W': (MOD_LSHIFT, 0x1A), 'X': (MOD_LSHIFT, 0x1B),
    'Y': (MOD_LSHIFT, 0x1C), 'Z': (MOD_LSHIFT, 0x1D),
    '1': (0x00, 0x1E), '2': (0x00, 0x1F), '3': (0x00, 0x20),
    '4': (0x00, 0x21), '5': (0x00, 0x22), '6': (0x00, 0x23),
    '7': (0x00, 0x24), '8': (0x00, 0x25), '9': (0x00, 0x26),
    '0': (0x00, 0x27), '\n': (0x00, 0x28), '\t': (0x00, 0x2B),
    ' ': (0x00, 0x2C), '.': (0x00, 0x37), ',': (0x00, 0x36),
    '-': (0x00, 0x2D), '=': (0x00, 0x2E), '/': (0x00, 0x38),
    '!': (MOD_LSHIFT, 0x1E), '@': (MOD_LSHIFT, 0x1F),
    '#': (MOD_LSHIFT, 0x20), '_': (MOD_LSHIFT, 0x2D),
    ':': (MOD_LSHIFT, 0x33), '"': (MOD_LSHIFT, 0x34),
}

_NULL_REPORT = bytes(8)


class DuckHunter:
    """Interprets DuckScript and injects keystrokes via /dev/hidg*."""

    def __init__(self, device_path: str, default_delay_ms: int = 50):
        self.device_path = device_path
        self.default_delay = default_delay_ms
        self._hid = None

    def run_file(self, script_path: str) -> None:
        """Parse and execute a DuckScript file."""
        try:
            with open(script_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"ERROR: Script not found: {script_path}", file=sys.stderr)
            sys.exit(1)

        try:
            self._hid = open(self.device_path, 'wb')
            for lineno, line in enumerate(lines, 1):
                self._execute_line(line.rstrip('\n'), lineno)
        except PermissionError:
            print(f"ERROR: Cannot open {self.device_path} – run as root.", file=sys.stderr)
            sys.exit(1)
        except FileNotFoundError:
            print(f"ERROR: HID device not found: {self.device_path}", file=sys.stderr)
            sys.exit(1)
        finally:
            if self._hid:
                self._hid.close()

    def _execute_line(self, line: str, lineno: int) -> None:
        stripped = line.strip()
        if not stripped or stripped.startswith('REM'):
            return

        parts = stripped.split(' ', 1)
        cmd = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ''

        if cmd == 'DELAY':
            try:
                time.sleep(int(arg) / 1000.0)
            except ValueError:
                print(f"WARN line {lineno}: invalid DELAY value '{arg}'")

        elif cmd == 'STRING':
            self._type_string(arg)

        elif cmd == 'ENTER':
            self._press_key(0x00, KEY_ENTER)

        elif cmd == 'TAB':
            self._press_key(0x00, KEY_TAB)

        elif cmd == 'BACKSPACE':
            self._press_key(0x00, KEY_BACKSPACE)

        elif cmd == 'DELETE':
            self._press_key(0x00, KEY_DELETE)

        elif cmd == 'ESCAPE':
            self._press_key(0x00, KEY_ESCAPE)

        elif cmd == 'UPARROW':
            self._press_key(0x00, KEY_UP)

        elif cmd == 'DOWNARROW':
            self._press_key(0x00, KEY_DOWN)

        elif cmd == 'LEFTARROW':
            self._press_key(0x00, KEY_LEFT)

        elif cmd == 'RIGHTARROW':
            self._press_key(0x00, KEY_RIGHT)

        elif cmd == 'CAPSLOCK':
            self._press_key(0x00, 0x39)

        elif cmd == 'GUI':
            kc = _KEY_NAMES.get(arg.upper(), 0x00)
            self._press_key(MOD_LMETA, kc)

        elif cmd == 'CTRL':
            kc = _KEY_NAMES.get(arg.upper(), 0x00)
            self._press_key(MOD_LCTRL, kc)

        elif cmd == 'ALT':
            kc = _KEY_NAMES.get(arg.upper(), 0x00)
            self._press_key(MOD_LALT, kc)

        elif cmd == 'SHIFT':
            kc = _KEY_NAMES.get(arg.upper(), 0x00)
            self._press_key(MOD_LSHIFT, kc)

        else:
            print(f"WARN line {lineno}: unknown command '{cmd}'")

    def _type_string(self, text: str) -> None:
        for ch in text:
            if ch in _CHAR_KEYMAP:
                mod, kc = _CHAR_KEYMAP[ch]
                self._press_key(mod, kc)
            time.sleep(self.default_delay / 1000.0)

    def _press_key(self, modifier: int, keycode: int) -> None:
        if self._hid is None:
            return
        report = bytes([modifier, 0x00, keycode, 0, 0, 0, 0, 0])
        self._hid.write(report)
        self._hid.flush()
        self._hid.write(_NULL_REPORT)
        self._hid.flush()
        time.sleep(self.default_delay / 1000.0)


def main():
    parser = argparse.ArgumentParser(
        description="NetHunter DuckHunter – DuckScript interpreter for HID injection"
    )
    parser.add_argument('-d', '--device', default='/dev/hidg0',
                        help='HID device (default: /dev/hidg0)')
    parser.add_argument('-f', '--file', required=True,
                        help='DuckScript payload file')
    parser.add_argument('--delay', type=int, default=50,
                        help='Default inter-key delay in ms (default: 50)')
    args = parser.parse_args()

    hunter = DuckHunter(args.device, args.delay)
    print(f"[DuckHunter] Running {args.file} on {args.device}")
    hunter.run_file(args.file)
    print("[DuckHunter] Done")


if __name__ == '__main__':
    main()
