from _imtui_buffer import Buffer
from _imtui_input import Key, MouseClick
from _imtui_term import Term


class UIContext:
    def __init__(self):
        self.active_id = None   # which widget has focus
        self.widget_counter = 0 # IDs issued this frame
        self.widget_count = 0   # IDs from previous frame (for nav wrap)
        self.buffer = Buffer()
        self.event = None       # current frame's unconsumed event
        self.cursor_x = 1
        self.cursor_y = 1
        self.text_cache = {}    # (x, y) -> (params, rendered_text)

    def cached_render(self, params, build):
        """Reuse the cached string at the cursor if `params` match last frame,
        otherwise call `build()` once and store the result."""
        key = (self.cursor_x, self.cursor_y)
        cached = self.text_cache.get(key)
        if cached is not None and cached[0] == params:
            return cached[1], True
        text = build()
        self.text_cache[key] = (params, text)
        return text, False

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


class UI:
    # -- layout helpers -------------------------------------------------
    @staticmethod
    def _resolve_pos(ctx: UIContext, x, y):
        if x is not None:
            ctx.cursor_x = x
        if y is not None:
            # allow relative position
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
        if is_focused and ctx.event in (Key.ENTER,):
            activated = True
            ctx.event = None

        # Mouse activation + hit-test
        elif isinstance(ctx.event, MouseClick):
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
    def clear_line(ctx: UIContext, y=None):
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
    def input(ctx: UIContext, value: str, label = "", width=20, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        if is_focused:
            ev = ctx.event
            if isinstance(ev, str) and len(ev) == 1 and 32 <= ord(ev) < 127:
                value += ev
                ctx.event = None
            elif ev == Key.BACKSPACE:
                value = value[:-1]
                ctx.event = None
        prefix = label + ": " if label else ""
        sufix = ('_' if is_focused else '')
        sufix += (" " * (width - len(value + sufix)))
        ctx.buffer.add_at(
            ctx.cursor_x,
            ctx.cursor_y,
            f"{prefix}{Term.UNDERLINE}{Term.BG_CYAN+Term.BLACK if is_focused else ''}{value}{sufix}{Term.RESET}",
        )
        ctx.cursor_y += 1
        return value

    @staticmethod
    def gauge(ctx: UIContext, label: str, value: int, max_val: int,
              width: int = 20, x=None, y=None):
        UI._resolve_pos(ctx, x, y)

        # Cache: only rebuild the string if these params changed since last frame.
        def build():
            ratio = max(0.0, min(1.0, value / max_val)) if max_val else 0
            filled = int(width * ratio)
            empty = width - filled
            bar = "█" * filled + "░" * empty
            pct = f"{int(ratio * 100):>3}%"
            return f"{label:<12} {Term.CYAN}{bar}{Term.RESET} {pct}"

        text, hit = ctx.cached_render((label, value, max_val, width), build)
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
        width = len(label) + 12

        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        # Edit with LEFT / RIGHT when focused
        if is_focused:
            if ctx.event == Key.LEFT:
                value = max(min_val, value - step)
                ctx.event = None
            elif ctx.event == Key.RIGHT or activated:
                value = min(max_val, value + step)
                ctx.event = None

        # Cache: only rebuild the string if these params changed since last frame.
        # Note: `is_focused` is included because it changes the look.
        def build():
            val_str = f"{value:02d}"
            prefix = " > " if is_focused else "   "
            if is_focused:
                val_render = f"{Term.BG_CYAN}{Term.BLACK}<{val_str}>{Term.RESET}"
            else:
                val_render = f" {val_str} "
            return f"{prefix}{label:<15} {val_render}"

        text, hit = ctx.cached_render((label, value, is_focused), build)
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
        total_w = 12+ 1 + bar_visual + 1 + value_w + 3
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, total_w, 1)

        if is_focused:
            if ctx.event == Key.LEFT:
                value = max(min_val, value - 1)
                ctx.event = None
            elif ctx.event == Key.RIGHT:
                value = min(max_val, value + 1)
                ctx.event = None

        # Cache: only rebuild the string if these params changed since last frame.
        def build():
            ratio = (value - min_val) / (max_val - min_val) if max_val != min_val else 0
            filled = int(width * ratio)
            empty = width - filled
            bar = "█" * filled + " " * empty
            bar_str = f"[{bar}]"
            if is_focused:
                bar_str = f"{Term.BG_BLUE}{Term.WHITE}{bar_str}{Term.RESET}"
            return f"{' > ' if is_focused else '   '}{label:<12} {bar_str} {value}"

        text, hit = ctx.cached_render((label, value, min_val, max_val, width, is_focused), build)

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
    def window(ctx: UIContext, lines: list[str],
               width: int = 30, x=None, y=None) -> None:
        UI._resolve_pos(ctx, x, y)

        border = Term.BLUE
        top = f"┌{'─' * (width - 2)}┐"

        bot = f"└{'─' * (width - 2)}┘"

        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{border}{top}{Term.RESET}")
        for i, line in enumerate(lines):
            ctx.buffer.add_at(
                ctx.cursor_x,
                ctx.cursor_y + 1 + i,
                f"{border}│{line.center(width - 2)}│{Term.RESET}",
            )
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1 + len(lines), f"{border}{bot}{Term.RESET}")
        ctx.cursor_y += 3
