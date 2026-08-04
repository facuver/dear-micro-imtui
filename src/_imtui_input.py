import sys

from _imtui_compat import asyncio, _MP


class Key:
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    ENTER = "ENTER"
    BACKSPACE = "BACKSPACE"
    TAB = "TAB"
    ESCAPE = "ESCAPE"


class MouseClick:
    __slots__ = ("x", "y", "button", "action")

    def __init__(self, x: int, y: int, button: str, action: str):
        self.x = x
        self.y = y
        self.button = button
        self.action = action

    def __repr__(self):
        return f"Mouse({self.button} {self.action} at {self.x},{self.y})"


class KeyBindings:
    """Event registry. Handlers receive (ctx, event) and return True to consume."""

    def __init__(self):
        self._early = {}   # key -> [handler, ...]
        self._late = {}    # key -> [handler, ...]
        self._help = {}

    def bind(self, key, handler, help="?", phase="early"):
        """Register a handler for an event key."""
        table = self._early if phase == "early" else self._late
        table.setdefault(key, []).append(handler)
        self._help.setdefault(key, help)

    def unbind(self, key, help="?", phase="early"):
        """Remove all handlers for a key."""
        table = self._early if phase == "early" else self._late
        table.pop(key, None)
        self._help.pop(key, None)

    def handle(self, ctx, event, phase="early"):
        """Run every handler for this event until one returns True."""
        table = self._early if phase == "early" else self._late
        for handler in table.get(event, []):
            if handler(ctx, event):
                return True
        return False

class InputReader:
    def __init__(self):
        self.sreader = asyncio.StreamReader(sys.stdin)

    @staticmethod
    def enable_mouse():
        sys.stdout.write("\x1b[?1000h")

    @staticmethod
    def disable_mouse():
        sys.stdout.write("\x1b[?1000l")

    async def read(self):
        if not _MP:
            await asyncio.sleep(1)
            return None

        while True:
            ch = await self.sreader.read(1)
            if not ch:
                continue

            # Escape sequences
            if ch == "\x1b":
                try:
                    nxt = await asyncio.wait_for(self.sreader.read(1), 0.2)
                    if nxt in ("[", "O"):
                        code = sys.stdin.read(1)
                        if code == "M":
                            b = sys.stdin.read(1)
                            x = sys.stdin.read(1)
                            y = sys.stdin.read(1)
                            return _parse_mouse(b, x, y)
                        if code == "A":
                            return Key.UP
                        if code == "B":
                            return Key.DOWN
                        if code == "C":
                            return Key.RIGHT
                        if code == "D":
                            return Key.LEFT
                except asyncio.TimeoutError:
                    return Key.ESCAPE

            # Control characters
            if ch in ("\r", "\n"):
                return Key.ENTER
            if ch in ("\x08", "\x7f"):
                return Key.BACKSPACE
            if ch == "\t":
                return Key.TAB

            # Printable
            if len(ch) == 1 and ord(ch) >= 32:
                return ch


def _parse_mouse(btn: str, xb: str, yb: str) -> MouseClick:
    b = ord(btn) - 32
    x = ord(xb) - 32
    y = ord(yb) - 32

    code = b & 3
    action = "PRESS"
    button = "LEFT"

    if code == 0:
        button = "LEFT"
    elif code == 1:
        button = "MIDDLE"
    elif code == 2:
        button = "RIGHT"
    elif code == 3:
        button = "NONE"
        action = "RELEASE"

    if b & 32:
        action = "MOVE"

    return MouseClick(x, y, button, action)
