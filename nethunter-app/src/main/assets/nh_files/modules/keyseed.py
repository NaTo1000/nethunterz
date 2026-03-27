#!/usr/bin/env python3
"""
keyseed.py - HID keyboard scan-code mapping table for NetHunterZ.

This module provides the key-seed lookup tables used by the NetHunter HID
(Human Interface Device) attack engine to translate printable ASCII characters
and common control sequences into USB HID scan codes that are injected via the
kernel's HID gadget driver.

Usage
-----
    from keyseed import KEYSEED, MODIFIER_KEYS, lookup_key

    scancode, modifier = lookup_key('A')
    # scancode=0x04, modifier=MODIFIER_SHIFT

References
----------
* USB HID Usage Tables 1.4 - Section 10 (Keyboard/Keypad page)
  https://www.usb.org/sites/default/files/hut1_4.pdf
"""

# ---------------------------------------------------------------------------
# Modifier key bitmask constants (USB HID boot-protocol modifier byte)
# ---------------------------------------------------------------------------
MODIFIER_NONE       = 0x00
MODIFIER_CTRL_LEFT  = 0x01
MODIFIER_SHIFT_LEFT = 0x02
MODIFIER_ALT_LEFT   = 0x04
MODIFIER_GUI_LEFT   = 0x08  # Windows / Command key
MODIFIER_CTRL_RIGHT = 0x10
MODIFIER_SHIFT_RIGHT= 0x20
MODIFIER_ALT_RIGHT  = 0x40  # AltGr
MODIFIER_GUI_RIGHT  = 0x80

# Convenience aliases
MODIFIER_CTRL  = MODIFIER_CTRL_LEFT
MODIFIER_SHIFT = MODIFIER_SHIFT_LEFT
MODIFIER_ALT   = MODIFIER_ALT_LEFT
MODIFIER_GUI   = MODIFIER_GUI_LEFT

# ---------------------------------------------------------------------------
# KEYSEED mapping: character → (HID usage ID, modifier bitmask)
#
# Lower-case letters a-z map to usage IDs 0x04-0x1D with no modifier.
# Upper-case letters require MODIFIER_SHIFT.
# Numbers 1-9 map to 0x1E-0x26; 0 maps to 0x27.
# ---------------------------------------------------------------------------
KEYSEED: dict = {
    # --- Letters ---
    'a': (0x04, MODIFIER_NONE),  'A': (0x04, MODIFIER_SHIFT),
    'b': (0x05, MODIFIER_NONE),  'B': (0x05, MODIFIER_SHIFT),
    'c': (0x06, MODIFIER_NONE),  'C': (0x06, MODIFIER_SHIFT),
    'd': (0x07, MODIFIER_NONE),  'D': (0x07, MODIFIER_SHIFT),
    'e': (0x08, MODIFIER_NONE),  'E': (0x08, MODIFIER_SHIFT),
    'f': (0x09, MODIFIER_NONE),  'F': (0x09, MODIFIER_SHIFT),
    'g': (0x0A, MODIFIER_NONE),  'G': (0x0A, MODIFIER_SHIFT),
    'h': (0x0B, MODIFIER_NONE),  'H': (0x0B, MODIFIER_SHIFT),
    'i': (0x0C, MODIFIER_NONE),  'I': (0x0C, MODIFIER_SHIFT),
    'j': (0x0D, MODIFIER_NONE),  'J': (0x0D, MODIFIER_SHIFT),
    'k': (0x0E, MODIFIER_NONE),  'K': (0x0E, MODIFIER_SHIFT),
    'l': (0x0F, MODIFIER_NONE),  'L': (0x0F, MODIFIER_SHIFT),
    'm': (0x10, MODIFIER_NONE),  'M': (0x10, MODIFIER_SHIFT),
    'n': (0x11, MODIFIER_NONE),  'N': (0x11, MODIFIER_SHIFT),
    'o': (0x12, MODIFIER_NONE),  'O': (0x12, MODIFIER_SHIFT),
    'p': (0x13, MODIFIER_NONE),  'P': (0x13, MODIFIER_SHIFT),
    'q': (0x14, MODIFIER_NONE),  'Q': (0x14, MODIFIER_SHIFT),
    'r': (0x15, MODIFIER_NONE),  'R': (0x15, MODIFIER_SHIFT),
    's': (0x16, MODIFIER_NONE),  'S': (0x16, MODIFIER_SHIFT),
    't': (0x17, MODIFIER_NONE),  'T': (0x17, MODIFIER_SHIFT),
    'u': (0x18, MODIFIER_NONE),  'U': (0x18, MODIFIER_SHIFT),
    'v': (0x19, MODIFIER_NONE),  'V': (0x19, MODIFIER_SHIFT),
    'w': (0x1A, MODIFIER_NONE),  'W': (0x1A, MODIFIER_SHIFT),
    'x': (0x1B, MODIFIER_NONE),  'X': (0x1B, MODIFIER_SHIFT),
    'y': (0x1C, MODIFIER_NONE),  'Y': (0x1C, MODIFIER_SHIFT),
    'z': (0x1D, MODIFIER_NONE),  'Z': (0x1D, MODIFIER_SHIFT),

    # --- Digits ---
    '1': (0x1E, MODIFIER_NONE),  '!': (0x1E, MODIFIER_SHIFT),
    '2': (0x1F, MODIFIER_NONE),  '@': (0x1F, MODIFIER_SHIFT),
    '3': (0x20, MODIFIER_NONE),  '#': (0x20, MODIFIER_SHIFT),
    '4': (0x21, MODIFIER_NONE),  '$': (0x21, MODIFIER_SHIFT),
    '5': (0x22, MODIFIER_NONE),  '%': (0x22, MODIFIER_SHIFT),
    '6': (0x23, MODIFIER_NONE),  '^': (0x23, MODIFIER_SHIFT),
    '7': (0x24, MODIFIER_NONE),  '&': (0x24, MODIFIER_SHIFT),
    '8': (0x25, MODIFIER_NONE),  '*': (0x25, MODIFIER_SHIFT),
    '9': (0x26, MODIFIER_NONE),  '(': (0x26, MODIFIER_SHIFT),
    '0': (0x27, MODIFIER_NONE),  ')': (0x27, MODIFIER_SHIFT),

    # --- Enter / control ---
    '\n': (0x28, MODIFIER_NONE),  # Enter
    '\t': (0x2B, MODIFIER_NONE),  # Tab
    ' ':  (0x2C, MODIFIER_NONE),  # Space
    '\b': (0x2A, MODIFIER_NONE),  # Backspace
    '\x1b': (0x29, MODIFIER_NONE),# Escape

    # --- Punctuation ---
    '-': (0x2D, MODIFIER_NONE),  '_': (0x2D, MODIFIER_SHIFT),
    '=': (0x2E, MODIFIER_NONE),  '+': (0x2E, MODIFIER_SHIFT),
    '[': (0x2F, MODIFIER_NONE),  '{': (0x2F, MODIFIER_SHIFT),
    ']': (0x30, MODIFIER_NONE),  '}': (0x30, MODIFIER_SHIFT),
    '\\': (0x31, MODIFIER_NONE), '|': (0x31, MODIFIER_SHIFT),
    ';': (0x33, MODIFIER_NONE),  ':': (0x33, MODIFIER_SHIFT),
    "'": (0x34, MODIFIER_NONE),  '"': (0x34, MODIFIER_SHIFT),
    '`': (0x35, MODIFIER_NONE),  '~': (0x35, MODIFIER_SHIFT),
    ',': (0x36, MODIFIER_NONE),  '<': (0x36, MODIFIER_SHIFT),
    '.': (0x37, MODIFIER_NONE),  '>': (0x37, MODIFIER_SHIFT),
    '/': (0x38, MODIFIER_NONE),  '?': (0x38, MODIFIER_SHIFT),
}

# ---------------------------------------------------------------------------
# Special / named key scan codes (for DuckyScript keywords)
# ---------------------------------------------------------------------------
SPECIAL_KEYS: dict = {
    'ENTER':     (0x28, MODIFIER_NONE),
    'ESC':       (0x29, MODIFIER_NONE),
    'BACKSPACE': (0x2A, MODIFIER_NONE),
    'TAB':       (0x2B, MODIFIER_NONE),
    'SPACE':     (0x2C, MODIFIER_NONE),
    'CAPSLOCK':  (0x39, MODIFIER_NONE),
    'F1':        (0x3A, MODIFIER_NONE),
    'F2':        (0x3B, MODIFIER_NONE),
    'F3':        (0x3C, MODIFIER_NONE),
    'F4':        (0x3D, MODIFIER_NONE),
    'F5':        (0x3E, MODIFIER_NONE),
    'F6':        (0x3F, MODIFIER_NONE),
    'F7':        (0x40, MODIFIER_NONE),
    'F8':        (0x41, MODIFIER_NONE),
    'F9':        (0x42, MODIFIER_NONE),
    'F10':       (0x43, MODIFIER_NONE),
    'F11':       (0x44, MODIFIER_NONE),
    'F12':       (0x45, MODIFIER_NONE),
    'HOME':      (0x4A, MODIFIER_NONE),
    'END':       (0x4D, MODIFIER_NONE),
    'INSERT':    (0x49, MODIFIER_NONE),
    'DELETE':    (0x4C, MODIFIER_NONE),
    'PAGEUP':    (0x4B, MODIFIER_NONE),
    'PAGEDOWN':  (0x4E, MODIFIER_NONE),
    'UP':        (0x52, MODIFIER_NONE),
    'DOWN':      (0x51, MODIFIER_NONE),
    'LEFT':      (0x50, MODIFIER_NONE),
    'RIGHT':     (0x4F, MODIFIER_NONE),
    'GUI':       (0x00, MODIFIER_GUI),
    'WINDOWS':   (0x00, MODIFIER_GUI),
    'CTRL':      (0x00, MODIFIER_CTRL),
    'SHIFT':     (0x00, MODIFIER_SHIFT),
    'ALT':       (0x00, MODIFIER_ALT),
}


def lookup_key(char: str) -> tuple:
    """
    Return the (HID usage ID, modifier bitmask) tuple for a single character.

    Parameters
    ----------
    char : str
        A single printable character or whitespace character.

    Returns
    -------
    tuple
        ``(usage_id: int, modifier: int)`` where *usage_id* is the USB HID
        key usage page 0x07 ID and *modifier* is the modifier byte bitmask.

    Raises
    ------
    KeyError
        If ``char`` has no mapping in :data:`KEYSEED`.
    """
    return KEYSEED[char]


def lookup_special(name: str) -> tuple:
    """
    Return the (HID usage ID, modifier bitmask) tuple for a named special key.

    Parameters
    ----------
    name : str
        Upper-case key name as used in DuckyScript (e.g., ``"ENTER"``, ``"GUI"``).

    Returns
    -------
    tuple
        ``(usage_id: int, modifier: int)``

    Raises
    ------
    KeyError
        If ``name`` is not in :data:`SPECIAL_KEYS`.
    """
    return SPECIAL_KEYS[name.upper()]


def string_to_keycodes(text: str) -> list:
    """
    Convert a plain-text string into a list of (usage_id, modifier) tuples.

    Characters with no mapping are silently skipped.

    Parameters
    ----------
    text : str
        The string to convert.

    Returns
    -------
    list of tuple
        Ordered list of ``(usage_id, modifier)`` pairs ready for HID injection.
    """
    result = []
    for ch in text:
        try:
            result.append(lookup_key(ch))
        except KeyError:
            pass  # Skip unmapped characters
    return result
