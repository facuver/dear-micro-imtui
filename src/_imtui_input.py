import sys

try:
    from select import poll, POLLIN
    _HAS_POLL = True
except ImportError:
    _HAS_POLL = False

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
        self._poll = None
        if _HAS_POLL:
            self._poll = poll()
            self._poll.register(sys.stdin, POLLIN)

    @staticmethod
    def enable_mouse():
        sys.stdout.write("\x1b[?1000h")

    @staticmethod
    def disable_mouse():
        sys.stdout.write("\x1b[?1000l")

    def _stdin_has_data(self):
        """Non-blocking check whether more bytes are waiting in stdin."""
        if self._poll is not None:
            return len(self._poll.poll(0)) > 0
        return False

    def _parse_char(self, ch):
        """Parse a single leading byte into an event (sync helper).
        Returns the event, or None if more bytes are needed (escape seq).
        """
        if ch == "\x1b":
            # Try to read rest of escape sequence synchronously.
            if self._stdin_has_data():
                nxt = sys.stdin.read(1)
                if nxt in ("[", "O"):
                    if self._stdin_has_data():
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
            return Key.ESCAPE

        if ch in ("\r", "\n"):
            return Key.ENTER
        if ch in ("\x08", "\x7f"):
            return Key.BACKSPACE
        if ch == "\t":
            return Key.TAB
        if len(ch) == 1 and ord(ch) >= 32:
            return ch
        return None

    async def read(self):
        """Read the next event, draining any buffered repeats.
        Returns only the last event so held keys don't accumulate lag."""

        while True:
            ch = await self.sreader.read(1)
            if not ch:
                continue

            # Escape sequences (async path for the first event)
            if ch == "\x1b":
                try:
                    nxt = await asyncio.wait_for(self.sreader.read(1), 0.2)
                    if nxt in ("[", "O"):
                        code = sys.stdin.read(1)
                        if code == "M":
                            b = sys.stdin.read(1)
                            x = sys.stdin.read(1)
                            y = sys.stdin.read(1)
                            event = _parse_mouse(b, x, y)
                        elif code == "A":
                            event = Key.UP
                        elif code == "B":
                            event = Key.DOWN
                        elif code == "C":
                            event = Key.RIGHT
                        elif code == "D":
                            event = Key.LEFT
                        else:
                            event = Key.ESCAPE
                    else:
                        event = Key.ESCAPE
                except asyncio.TimeoutError:
                    event = Key.ESCAPE
            elif ch in ("\r", "\n"):
                event = Key.ENTER
            elif ch in ("\x08", "\x7f"):
                event = Key.BACKSPACE
            elif ch == "\t":
                event = Key.TAB
            elif len(ch) == 1 and ord(ch) >= 32:
                event = ch
            else:
                continue

            # Drain: consume all buffered bytes without yielding,
            # keeping only the last parsed event.
            while self._stdin_has_data():
                c = sys.stdin.read(1)
                if c:
                    parsed = self._parse_char(c)
                    if parsed is not None:
                        event = parsed

            return event
                


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
