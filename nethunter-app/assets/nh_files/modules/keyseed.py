#!/usr/bin/env python3
"""
keyseed.py – HID key seed generator for NetHunter DuckHunter.

Generates properly formatted HID key reports from plain-text payloads
and writes them to the USB gadget HID device node.

Usage:
    python3 keyseed.py -d /dev/hidg0 -p "Hello, World!"
    python3 keyseed.py -d /dev/hidg0 -f payload.txt
"""

import argparse
import sys
import time

# USB HID keyboard modifier byte masks
MOD_NONE       = 0x00
MOD_LCTRL      = 0x01
MOD_LSHIFT     = 0x02
MOD_LALT       = 0x04
MOD_LMETA      = 0x08
MOD_RCTRL      = 0x10
MOD_RSHIFT     = 0x20
MOD_RALT       = 0x40
MOD_RMETA      = 0x80

# US QWERTY key-code lookup table (character → (modifier, keycode))
_KEYMAP = {
    'a': (MOD_NONE,   0x04), 'b': (MOD_NONE,   0x05),
    'c': (MOD_NONE,   0x06), 'd': (MOD_NONE,   0x07),
    'e': (MOD_NONE,   0x08), 'f': (MOD_NONE,   0x09),
    'g': (MOD_NONE,   0x0A), 'h': (MOD_NONE,   0x0B),
    'i': (MOD_NONE,   0x0C), 'j': (MOD_NONE,   0x0D),
    'k': (MOD_NONE,   0x0E), 'l': (MOD_NONE,   0x0F),
    'm': (MOD_NONE,   0x10), 'n': (MOD_NONE,   0x11),
    'o': (MOD_NONE,   0x12), 'p': (MOD_NONE,   0x13),
    'q': (MOD_NONE,   0x14), 'r': (MOD_NONE,   0x15),
    's': (MOD_NONE,   0x16), 't': (MOD_NONE,   0x17),
    'u': (MOD_NONE,   0x18), 'v': (MOD_NONE,   0x19),
    'w': (MOD_NONE,   0x1A), 'x': (MOD_NONE,   0x1B),
    'y': (MOD_NONE,   0x1C), 'z': (MOD_NONE,   0x1D),
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
    '1': (MOD_NONE,   0x1E), '2': (MOD_NONE,   0x1F),
    '3': (MOD_NONE,   0x20), '4': (MOD_NONE,   0x21),
    '5': (MOD_NONE,   0x22), '6': (MOD_NONE,   0x23),
    '7': (MOD_NONE,   0x24), '8': (MOD_NONE,   0x25),
    '9': (MOD_NONE,   0x26), '0': (MOD_NONE,   0x27),
    '\n': (MOD_NONE,  0x28), '\t': (MOD_NONE,  0x2B),
    ' ': (MOD_NONE,   0x2C), '-': (MOD_NONE,   0x2D),
    '=': (MOD_NONE,   0x2E), '[': (MOD_NONE,   0x2F),
    ']': (MOD_NONE,   0x30), '\\': (MOD_NONE,  0x31),
    ';': (MOD_NONE,   0x33), "'": (MOD_NONE,   0x34),
    '`': (MOD_NONE,   0x35), ',': (MOD_NONE,   0x36),
    '.': (MOD_NONE,   0x37), '/': (MOD_NONE,   0x38),
    '!': (MOD_LSHIFT, 0x1E), '@': (MOD_LSHIFT, 0x1F),
    '#': (MOD_LSHIFT, 0x20), '$': (MOD_LSHIFT, 0x21),
    '%': (MOD_LSHIFT, 0x22), '^': (MOD_LSHIFT, 0x23),
    '&': (MOD_LSHIFT, 0x24), '*': (MOD_LSHIFT, 0x25),
    '(': (MOD_LSHIFT, 0x26), ')': (MOD_LSHIFT, 0x27),
    '_': (MOD_LSHIFT, 0x2D), '+': (MOD_LSHIFT, 0x2E),
    '{': (MOD_LSHIFT, 0x2F), '}': (MOD_LSHIFT, 0x30),
    '|': (MOD_LSHIFT, 0x31), ':': (MOD_LSHIFT, 0x33),
    '"': (MOD_LSHIFT, 0x34), '~': (MOD_LSHIFT, 0x35),
    '<': (MOD_LSHIFT, 0x36), '>': (MOD_LSHIFT, 0x37),
    '?': (MOD_LSHIFT, 0x38),
}

_NULL_REPORT = bytes(8)


def char_to_report(ch: str) -> bytes:
    """Convert a single character to an 8-byte HID keyboard report."""
    if ch not in _KEYMAP:
        return _NULL_REPORT
    mod, keycode = _KEYMAP[ch]
    # Report: [modifier, reserved, key1, key2, key3, key4, key5, key6]
    return bytes([mod, 0x00, keycode, 0x00, 0x00, 0x00, 0x00, 0x00])


def send_string(device_path: str, text: str, delay_ms: int = 50) -> None:
    """Write a string to the HID device character by character."""
    try:
        with open(device_path, 'wb') as hid:
            for ch in text:
                report = char_to_report(ch)
                if report != _NULL_REPORT:
                    hid.write(report)
                    hid.flush()
                hid.write(_NULL_REPORT)
                hid.flush()
                time.sleep(delay_ms / 1000.0)
    except PermissionError:
        print(f"ERROR: No permission to write to {device_path}. Run as root.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: HID device not found: {device_path}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="NetHunter keyseed – HID keyboard injection utility"
    )
    parser.add_argument('-d', '--device', default='/dev/hidg0',
                        help='HID device path (default: /dev/hidg0)')
    parser.add_argument('-p', '--payload', help='String payload to inject')
    parser.add_argument('-f', '--file', help='File containing the payload')
    parser.add_argument('--delay', type=int, default=50,
                        help='Inter-key delay in milliseconds (default: 50)')
    args = parser.parse_args()

    if args.payload:
        payload = args.payload
    elif args.file:
        try:
            with open(args.file) as fh:
                payload = fh.read()
        except FileNotFoundError:
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"[keyseed] Injecting {len(payload)} characters via {args.device}")
    send_string(args.device, payload, args.delay)
    print("[keyseed] Done")


if __name__ == '__main__':
    main()
