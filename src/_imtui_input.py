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
        self.sreader  = None
        if _MP:
            stream_reader_cls = getattr(asyncio, "StreamReader", None)
            if stream_reader_cls is not None:
                self.sreader = stream_reader_cls(sys.stdin)

    @staticmethod
    def enable_mouse():
        sys.stdout.write("\x1b[?1000h")

    @staticmethod
    def disable_mouse():
        sys.stdout.write("\x1b[?1000l")

    # Time budget (seconds) to wait for the rest of an escape sequence.
    # Generous enough to survive a busy/slow event loop, but still short
    # enough that a bare ESC keypress feels instant.
    ESC_SEQ_TIMEOUT = 0.3

    async def _read_seq_byte(self, reader):
        """Read one byte of an in-flight escape sequence.

        Returns None if nothing arrives within ESC_SEQ_TIMEOUT, which means
        the user really did just press ESC (or the terminal sent a partial
        sequence). Using a wall-clock budget instead of a tiny fixed timeout
        keeps us non-blocking while tolerating slow event loop iterations.
        """
        try:
            return await asyncio.wait_for(reader.read(1), self.ESC_SEQ_TIMEOUT)
        except asyncio.TimeoutError:
            return None

    async def read(self):

        reader = self.sreader
        if reader is None:
            await asyncio.sleep(1)
            return None

        while True:
            ch = await reader.read(1)
            if not ch:
                continue

            # Escape sequences
            if ch == "\x1b":
                nxt = await self._read_seq_byte(reader)
                if nxt is None:
                    return Key.ESCAPE
                if nxt in ("[", "O"):
                    code = await self._read_seq_byte(reader)
                    if code is None:
                        return Key.ESCAPE
                    if code == "M":
                        b = await self._read_seq_byte(reader)
                        x = await self._read_seq_byte(reader)
                        y = await self._read_seq_byte(reader)
                        if None in (b, x, y):
                            continue
                        return _parse_mouse(b, x, y)
                    if code == "A":
                        return Key.UP
                    if code == "B":
                        return Key.DOWN
                    if code == "C":
                        return Key.RIGHT
                    if code == "D":
                        return Key.LEFT
                continue

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



def _as_ord(ch) -> int:
    if isinstance(ch, int):
        return ch
    if isinstance(ch, (bytes, bytearray)):
        return ch[0] if ch else 0
    return ord(ch)


def _parse_mouse(btn, xb, yb) -> MouseClick:
    b = _as_ord(btn) - 32
    x = _as_ord(xb) - 32
    y = _as_ord(yb) - 32

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
