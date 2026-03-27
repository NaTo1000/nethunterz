#!/usr/bin/env python3
"""
keyseed.py - HID Ducky Script key seed module for NetHunter.
Provides keystroke timing, key code mapping, and HID payload generation
for BadUSB / DuckyScript execution on the Flipper Zero.
"""

import time
import struct
import os
from typing import Optional, List, Tuple

# HID Usage IDs for standard keys (US QWERTY layout)
KEY_MAP = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08,
    'f': 0x09, 'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D,
    'k': 0x0E, 'l': 0x0F, 'm': 0x10, 'n': 0x11, 'o': 0x12,
    'p': 0x13, 'q': 0x14, 'r': 0x15, 's': 0x16, 't': 0x17,
    'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B, 'y': 0x1C,
    'z': 0x1D,

    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,

    'ENTER':     0x28, 'RETURN':    0x28,
    'ESCAPE':    0x29, 'ESC':       0x29,
    'BACKSPACE': 0x2A, 'DELETE':    0x2A,
    'TAB':       0x2B,
    'SPACE':     0x2C, ' ':         0x2C,

    '-': 0x2D, '_': 0x2D,
    '=': 0x2E, '+': 0x2E,
    '[': 0x2F, '{': 0x2F,
    ']': 0x30, '}': 0x30,
    '\\':0x31, '|': 0x31,
    ';': 0x33, ':': 0x33,
    "'": 0x34, '"': 0x34,
    '`': 0x35, '~': 0x35,
    ',': 0x36, '<': 0x36,
    '.': 0x37, '>': 0x37,
    '/': 0x38, '?': 0x38,

    'F1':  0x3A, 'F2':  0x3B, 'F3':  0x3C, 'F4':  0x3D,
    'F5':  0x3E, 'F6':  0x3F, 'F7':  0x40, 'F8':  0x41,
    'F9':  0x42, 'F10': 0x43, 'F11': 0x44, 'F12': 0x45,

    'PRINTSCREEN': 0x46, 'SCROLLLOCK': 0x47, 'PAUSE': 0x48,
    'INSERT': 0x49, 'HOME': 0x4A, 'PAGEUP': 0x4B,
    'DEL':    0x4C, 'END':  0x4D, 'PAGEDOWN': 0x4E,

    'RIGHT': 0x4F, 'LEFT': 0x50, 'DOWN': 0x51, 'UP': 0x52,

    'NUMLOCK': 0x53,
    'GUI': 0xE3, 'WINDOWS': 0xE3, 'COMMAND': 0xE3,
    'CTRL': 0xE0, 'CONTROL': 0xE0,
    'ALT': 0xE2,
    'SHIFT': 0xE1,
    'RSHIFT': 0xE5, 'RCTRL': 0xE4, 'RALT': 0xE6, 'RGUI': 0xE7,
}

# Modifier bitmasks
MODIFIER_NONE   = 0x00
MODIFIER_CTRL   = 0x01
MODIFIER_SHIFT  = 0x02
MODIFIER_ALT    = 0x04
MODIFIER_GUI    = 0x08
MODIFIER_RCTRL  = 0x10
MODIFIER_RSHIFT = 0x20
MODIFIER_RALT   = 0x40
MODIFIER_RGUI   = 0x80

# Characters that require SHIFT modifier
SHIFT_CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+{}|:"<>?~')


class HIDReport:
    """Represents a single USB HID keyboard report (8 bytes)."""

    def __init__(self, modifier: int = 0, key: int = 0):
        self.modifier = modifier
        self.reserved = 0
        self.key = key
        self.reserved_keys = [0] * 5  # Keys 2-6

    def to_bytes(self) -> bytes:
        return struct.pack('BBBBBBBB',
            self.modifier,
            self.reserved,
            self.key,
            *self.reserved_keys
        )

    @staticmethod
    def release() -> bytes:
        """Empty (key release) report."""
        return bytes(8)


class KeySeed:
    """
    Generates HID keystroke sequences from DuckyScript-like text.
    Provides timing randomization to evade detection.
    """

    def __init__(self, delay_ms: int = 50, jitter_ms: int = 10):
        """
        Args:
            delay_ms:  Base delay between keystrokes in milliseconds.
            jitter_ms: Random jitter to add to delays for naturalness.
        """
        self.delay_ms  = delay_ms
        self.jitter_ms = jitter_ms
        self.seed      = int.from_bytes(os.urandom(4), 'little')

    def _jittered_delay(self) -> float:
        """Return a jittered delay in seconds."""
        self.seed = (self.seed * 1664525 + 1013904223) & 0xFFFFFFFF
        jitter = (self.seed & 0xFFFF) / 0xFFFF * self.jitter_ms
        return (self.delay_ms + jitter) / 1000.0

    def char_to_hid(self, char: str) -> Tuple[int, int]:
        """Convert a character to (modifier, keycode) pair."""
        if char in SHIFT_CHARS:
            return (MODIFIER_SHIFT, KEY_MAP.get(char.lower(), 0))
        return (0, KEY_MAP.get(char, 0))

    def string_to_reports(self, text: str) -> List[bytes]:
        """Convert a string to a list of HID reports."""
        reports = []
        for char in text:
            modifier, keycode = self.char_to_hid(char)
            if keycode == 0:
                continue
            reports.append(HIDReport(modifier, keycode).to_bytes())
            reports.append(HIDReport.release())
        return reports

    def parse_duckyscript_line(self, line: str) -> List[bytes]:
        """Parse a single DuckyScript line and return HID reports."""
        line = line.strip()
        if not line or line.startswith('REM') or line.startswith('#'):
            return []

        parts = line.split(' ', 1)
        command = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ''

        if command == 'STRING':
            return self.string_to_reports(args)

        elif command == 'DELAY':
            try:
                ms = int(args)
                time.sleep(ms / 1000.0)
            except ValueError:
                pass
            return []

        elif command in ('ENTER', 'RETURN'):
            r = HIDReport(0, KEY_MAP['ENTER'])
            return [r.to_bytes(), HIDReport.release()]

        elif command in KEY_MAP:
            # Modifier combination (e.g., CTRL ALT DELETE)
            modifier = 0
            keycode = 0
            for token in [command] + args.split():
                if token in ('CTRL', 'CONTROL', 'RCTRL'):
                    modifier |= MODIFIER_CTRL
                elif token in ('SHIFT', 'RSHIFT'):
                    modifier |= MODIFIER_SHIFT
                elif token in ('ALT', 'RALT'):
                    modifier |= MODIFIER_ALT
                elif token in ('GUI', 'WINDOWS', 'COMMAND', 'RGUI'):
                    modifier |= MODIFIER_GUI
                elif token in KEY_MAP:
                    keycode = KEY_MAP[token]
            if keycode > 0:
                r = HIDReport(modifier, keycode)
                return [r.to_bytes(), HIDReport.release()]

        return []

    def generate_payload(self, ducky_script: str) -> bytes:
        """Convert a full DuckyScript to a binary HID payload."""
        payload = bytearray()
        for line in ducky_script.splitlines():
            reports = self.parse_duckyscript_line(line)
            for report in reports:
                payload.extend(report)
        return bytes(payload)


def main():
    """Demo: generate a simple HID payload."""
    seed = KeySeed(delay_ms=50, jitter_ms=15)

    script = """
REM NetHunter HID test payload
DELAY 1000
GUI r
DELAY 500
STRING notepad
ENTER
DELAY 1000
STRING Hello from NetHunter!
ENTER
"""

    payload = seed.generate_payload(script)
    print(f"Generated HID payload: {len(payload)} bytes, {len(payload)//8} reports")
    print("First 3 reports (hex):")
    for i in range(min(3, len(payload) // 8)):
        chunk = payload[i*8:(i+1)*8]
        print(f"  Report {i+1}: {chunk.hex(' ')}")


if __name__ == '__main__':
    main()
