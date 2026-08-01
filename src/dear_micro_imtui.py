import sys

# ------------------------------------------------------------------
# 1. MicroPython / CPython compatibility
# ------------------------------------------------------------------
try:
    import uasyncio as asyncio
    _MP = True
except ImportError:
    import asyncio
    _MP = False


async def _sleep_ms(ms):
    """Cross-platform sleep."""
    if _MP:
        await asyncio.sleep_ms(ms)
    else:
        await asyncio.sleep(ms / 1000.0)


# ------------------------------------------------------------------
# 2. Terminal ANSI helpers
# ------------------------------------------------------------------
class Term:
    # Resets
    RESET = "\x1b[0m"

    # Styles
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    ITALIC = "\x1b[3m"
    UNDERLINE = "\x1b[4m"
    BLINK = "\x1b[5m"
    REVERSE = "\x1b[7m"
    HIDDEN = "\x1b[8m"

    # Foreground Colors
    BLACK = "\x1b[30m"
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"
    WHITE = "\x1b[37m"

    # Bright Foreground Colors
    BRIGHT_BLACK = "\x1b[90m"
    BRIGHT_RED = "\x1b[91m"
    BRIGHT_GREEN = "\x1b[92m"
    BRIGHT_YELLOW = "\x1b[93m"
    BRIGHT_BLUE = "\x1b[94m"
    BRIGHT_MAGENTA = "\x1b[95m"
    BRIGHT_CYAN = "\x1b[96m"
    BRIGHT_WHITE = "\x1b[97m"

    # Background Colors
    BG_BLACK = "\x1b[40m"
    BG_RED = "\x1b[41m"
    BG_GREEN = "\x1b[42m"
    BG_YELLOW = "\x1b[43m"
    BG_BLUE = "\x1b[44m"
    BG_MAGENTA = "\x1b[45m"
    BG_CYAN = "\x1b[46m"
    BG_WHITE = "\x1b[47m"

    @classmethod
    def clear(cls):
        sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")

    @classmethod
    def hide_cursor(cls):
        sys.stdout.write("\x1b[?25l")

    @classmethod
    def show_cursor(cls):
        sys.stdout.write("\x1b[?25h")


# ------------------------------------------------------------------
# 3. Render buffer
# ------------------------------------------------------------------
class Buffer:
    def __init__(self):
        self.ops = []

    def add_at(self, x: int, y: int, text: str):
        """Move cursor to (x,y), draw text, clear rest of line."""
        self.ops.append(f"\x1b[{y};{x}H{text}\x1b[K")

    def flush(self):
        # Term.clear()
        if not self.ops:
            return
        sys.stdout.write("\x1b[H" + "".join(self.ops) + "\x1b[J")
        self.ops.clear()


# ------------------------------------------------------------------
# 4. Input abstraction (keyboard + X10 mouse)
# ------------------------------------------------------------------
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
        self._help ={}

    def bind(self, key, handler,help="?", phase="early"):
        """Register a handler for an event key."""
        table = self._early if phase == "early" else self._late
        table.setdefault(key, []).append(handler)
        self._help.setdefault(key,help)

    def unbind(self, key,help="?", phase="early"):
        """Remove all handlers for a key."""
        table = self._early if phase == "early" else self._late
        table.pop(key, None)
        self._help.pop(key,None)


    def handle(self, ctx, event, phase="early"):
        """Run every handler for this event until one returns True."""
        table = self._early if phase == "early" else self._late
        for handler in table.get(event, []):
            if handler(ctx, event):
                return True
        return False

class InputReader:
    def __init__(self):
        if _MP:
            self.sreader = asyncio.StreamReader(sys.stdin)
        else:
            self.sreader = None

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
                    nxt = await asyncio.wait_for(self.sreader.read(1), 0.05)
                    if nxt in ("[", "O"):
                        code = await self.sreader.read(1)
                        if code == "M":
                            b = await self.sreader.read(1)
                            x = await self.sreader.read(1)
                            y = await self.sreader.read(1)
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


# ------------------------------------------------------------------
# 5. UI Context (immediate-mode state machine)
# ------------------------------------------------------------------
class UIContext:
    def __init__(self):
        self.active_id = None   # which widget has focus
        self.widget_counter = 0 # IDs issued this frame
        self.widget_count = 0   # IDs from previous frame (for nav wrap)
        self.buffer = Buffer()
        self.event = None       # current frame's unconsumed event
        self.cursor_x = 1
        self.cursor_y = 1

    def begin_frame(self, event):
        self.widget_count = self.widget_counter
        self.widget_counter = 0
        self.event = event
        self.cursor_x = 1
        self.cursor_y = 1

        # Clamp focus if widget count changed (dynamic UIs)
        if self.widget_count > 0 and self.active_id is not None:
            self.active_id %= self.widget_count
        elif self.widget_count == 0:
            self.active_id = None

    def end_frame(self):
        self.event = None
        self.buffer.flush()

    def register_focusable(self):
        w_id = self.widget_counter
        self.widget_counter += 1
        if self.active_id is None and self.widget_count > 0:
            self.active_id = 0
        is_focused = (w_id == self.active_id)
        return w_id, is_focused


# ------------------------------------------------------------------
# 6. Widget suite
# ------------------------------------------------------------------
class UI:
    # -- layout helpers -------------------------------------------------
    @staticmethod
    def _resolve_pos(ctx: UIContext, x, y):
        if x is not None:
            ctx.cursor_x = x
        if y is not None:
            #allow relative position
            if y < 0:
                ctx.cursor_y += y
            else:
                ctx.cursor_y = y

    # -- primitive ------------------------------------------------------
    @staticmethod
    def clickable(ctx: UIContext, x: int, y: int, width: int, height: int = 1):
        """
        Lowest-level interactable primitive.
        Returns (is_focused, activated_this_frame).
        """
        w_id, is_focused = ctx.register_focusable()
        activated = False

        # Keyboard activation
        if is_focused and ctx.event in (Key.ENTER, " "):
            activated = True
            ctx.event = None

        # Mouse activation + hit-test
        if isinstance(ctx.event, MouseClick):
            m = ctx.event
            if m.action == "PRESS" and m.button == "LEFT":
                if x <= m.x < x + width and y <= m.y < y + height:
                    ctx.active_id = w_id
                    is_focused = True
                    activated = True
                    ctx.event = None

        return is_focused, activated

    # -- non-interactive ------------------------------------------------
    @staticmethod
    def label(ctx: UIContext, text: str, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1

    @staticmethod
    def clear_line(ctx: UIContext,  y=None):
        UI._resolve_pos(ctx, None, y)
        ctx.buffer.add_at(1, ctx.cursor_y, "")

    @staticmethod
    def divider(ctx: UIContext, width: int = 34, char: str = "─", x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y,
                          f"{Term.DIM}{char * width}{Term.RESET}")
        ctx.cursor_y += 1

    @staticmethod
    def badge(ctx: UIContext, label: str, value: str, color=Term.GREEN, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        text = (f"{Term.DIM}[{Term.RESET}{label}: "
                f"{color}{Term.BOLD}{value}{Term.RESET}{Term.DIM}]{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1

    @staticmethod
    def gauge(ctx: UIContext, label: str, value: int, max_val: int,
              width: int = 20, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        ratio = max(0.0, min(1.0, value / max_val)) if max_val else 0
        filled = int(width * ratio)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        pct = f"{int(ratio * 100):>3}%"
        text = f"{label:<12} {Term.CYAN}{bar}{Term.RESET} {pct}"
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1

    # -- interactive ----------------------------------------------------
    @staticmethod
    def button(ctx: UIContext, label: str, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        width = len(label) + 4
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        bg = Term.BG_BLUE if is_focused else ""
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y,
                          f"{bg}[ {label} ]{Term.RESET}")
        ctx.cursor_y += 1
        return activated

    @staticmethod
    def checkbox(ctx: UIContext, label: str, checked: bool, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        mark = "X" if checked else " "
        text = f"[{mark}] {label}"
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, len(text), 1)

        if activated:
            checked = not checked

        bg = Term.BG_BLUE if is_focused else ""
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{bg}{text}{Term.RESET}")
        ctx.cursor_y += 1
        return checked

    @staticmethod
    def toggle(ctx: UIContext, label: str, active: bool, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        width = len(label) + 10
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        if activated:
            active = not active

        prefix = " > " if is_focused else "   "
        if active:
            status = f"{Term.BG_GREEN}{Term.BLACK} ON {Term.RESET}"
        else:
            status = f"{Term.BG_RED}{Term.WHITE} OFF {Term.RESET}"

        text = f"{prefix}{label:<15} {status}"
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1
        return active

    @staticmethod
    def number_stepper(ctx: UIContext, label: str, value: int,
                       min_val: int = 0, max_val: int = 99, step: int = 1,
                       x=None, y=None) -> int:
        UI._resolve_pos(ctx, x, y)
        val_str = f"{value:02d}"
        width = len(label) + 12

        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        # Edit with LEFT / RIGHT when focused
        if is_focused:
            if ctx.event == Key.LEFT :
                value = max(min_val, value - step)
                ctx.event = None
            elif ctx.event == Key.RIGHT or activated:
                value = min(max_val, value + step)
                ctx.event = None

        prefix = " > " if is_focused else "   "
        if is_focused:
            val_render = f"{Term.BG_CYAN}{Term.BLACK}<{val_str}>{Term.RESET}"
        else:
            val_render = f" {val_str} "

        text = f"{prefix}{label:<15} {val_render}"
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1
        return value

    @staticmethod
    def slider(ctx: UIContext, label: str, value: int,
               min_val: int = 0, max_val: int = 100, width: int = 20,
               x=None, y=None) -> int:
        UI._resolve_pos(ctx, x, y)
        bar_visual = width + 2  # [....]
        value_w = len(str(max_val))
        total_w = len(label) + 1 + bar_visual + 1 + value_w + 3

        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, total_w, 1)

        if is_focused:
            if ctx.event == Key.LEFT:
                value = max(min_val, value - 1)
                ctx.event = None
            elif ctx.event == Key.RIGHT:
                value = min(max_val, value + 1)
                ctx.event = None

        ratio = (value - min_val) / (max_val - min_val) if max_val != min_val else 0
        filled = int(width * ratio)
        empty = width - filled
        bar = "█" * filled + " " * empty
        bar_str = f"[{bar}]"
        if is_focused:
            bar_str = f"{Term.BG_BLUE}{Term.WHITE}{bar_str}{Term.RESET}"

        text = f"{' > ' if is_focused else '   '}{label:<12} {bar_str} {value}"
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)
        ctx.cursor_y += 1
        return value

    @staticmethod
    def card(ctx: UIContext, title: str, subtitle: str,
             width: int = 30, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 3)

        border = Term.GREEN if is_focused else Term.DIM

        # Top
        inner = width - 4
        left = max(0, (inner - len(title)) // 2)
        right = max(0, inner - len(title) - left)
        top = f"┌{'─' * left} {title} {'─' * right}┐"

        # Middle
        mid_inner = width - 2
        mleft = max(0, (mid_inner - len(subtitle)) // 2)
        mright = max(0, mid_inner - len(subtitle) - mleft)
        mid = f"│{' ' * mleft}{subtitle}{' ' * mright}│"

        # Bottom
        bot = f"└{'─' * (width - 2)}┘"

        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{border}{top}{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1, f"{border}{mid}{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 2, f"{border}{bot}{Term.RESET}")
        ctx.cursor_y += 3
        return activated

    @staticmethod
    def window(ctx: UIContext,   lines: list[str],
                width: int = 30, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)

        border = Term.BLUE
        top = f"┌{'─' * (width - 2)}┐"


        bot = f"└{'─' * (width - 2)}┘"


        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{border}{top}{Term.RESET}")
        for i,line in enumerate(lines):

            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1 + i, f"{border}│{line.center(width-2)}│{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1+ len(lines), f"{border}{bot}{Term.RESET}")
        ctx.cursor_y += 3


# ------------------------------------------------------------------
# 7. Application base class
# ------------------------------------------------------------------
class App:
    def __init__(self, fps: int = 30):
        self.ctx = UIContext()
        self.reader = InputReader()
        self.fps_ms = int(1000 / fps)
        self._latest_event = None
        self._running = True

        self.keybindings = KeyBindings()
        self._setup_default_keybindings()

    async def _input_loop(self):
        while self._running:
            event = await self.reader.read()
            if event is not None:
                self._latest_event = event

    async def _ui_loop(self):
        while self._running:
            event = self._latest_event
            self._latest_event = None

            self.ctx.begin_frame(event)

            # PHASE 1: Early bindings (global shortcuts)
            if self.ctx.event and self.keybindings.handle(self.ctx, self.ctx.event, "early"):
                self.ctx.event = None

            self.on_ui()

            # PHASE 2: Late bindings (navigation & overrides)
            if self.ctx.event and self.keybindings.handle(self.ctx, self.ctx.event, "late"):
                self.ctx.event = None

            self.ctx.end_frame()
            await _sleep_ms(self.fps_ms)


    def on_ui(self):
        raise NotImplementedError("Override on_ui() in your App subclass.")

    def _nav_prev(self, ctx, event):
            if ctx.widget_count > 0 and ctx.active_id is not None:
                ctx.active_id = (ctx.active_id - 1) % ctx.widget_count
            return True

    def _nav_next(self, ctx, event):
        if ctx.widget_count > 0 and ctx.active_id is not None:
            ctx.active_id = (ctx.active_id + 1) % ctx.widget_count
        return True

    def _setup_default_keybindings(self):
        # Early: global shortcuts (run before widgets)
        self.keybindings.bind("r", lambda ctx, e: Term.clear() or True, help="REDRAW")
        self.keybindings.bind("q", lambda ctx, e: self._quit() or True,help="QUIT")

        # Late: default focus navigation (run only if widgets didn't eat the event)
        self.keybindings.bind(Key.UP,   self._nav_prev, phase="late",help="NEXT")
        self.keybindings.bind(Key.DOWN, self._nav_next, phase="late",help="PREV")

    def _quit(self):
        self._running = False


    def run(self):
        Term.clear()
        Term.hide_cursor()
        self.reader.enable_mouse()
        try:
            if _MP:
                asyncio.run(asyncio.gather(self._input_loop(), self._ui_loop()))
            else:
                asyncio.run(self._ui_loop())
        finally:
            self.reader.disable_mouse()
            Term.show_cursor()
            Term.clear()
            print("App exited.")
