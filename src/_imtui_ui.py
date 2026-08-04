from _imtui_buffer import Buffer
from _imtui_input import Key, MouseClick
from _imtui_term import Term
import micropython


class UIContext:
    __slots__ = (
        "active_id",
        "widget_counter",
        "widget_count",
        "buffer",
        "event",
        "cursor_x",
        "cursor_y",
        "text_cache",
        "_last_frame_bottom",
        "_force_full_redraw",
        "_force_full_redraw_next",
        "_event_is_mouse",
        "_mouse_event",
    )

    def __init__(self):
        self.active_id = None   # which widget has focus
        self.widget_counter = 0 # IDs issued this frame
        self.widget_count = 0   # IDs from previous frame (for nav wrap)
        self.buffer = Buffer()
        self.event = None       # current frame's unconsumed event
        self.cursor_x = 1
        self.cursor_y = 1
        # key: packed (y << 16) | x -> (params, rendered_text)
        self.text_cache = {}
        self._last_frame_bottom = 0
        self._force_full_redraw = False
        self._force_full_redraw_next = False

        # pre-decoded event hints for faster widget checks
        self._event_is_mouse = False
        self._mouse_event = None

    @micropython.native
    def _cache_key(self):
        return (self.cursor_y << 16) | self.cursor_x

    @micropython.native
    def cache_get(self, params):
        key = self._cache_key()
        cached = self.text_cache.get(key)
        if cached is not None and cached[0] == params:
            return cached[1]
        return None

    @micropython.native
    def cache_store(self, params, text):
        self.text_cache[self._cache_key()] = (params, text)

    def begin_frame(self, event):
        # Apply any redraw requested after the previous frame's draw phase.
        if self._force_full_redraw_next:
            self._force_full_redraw = True
            self._force_full_redraw_next = False
        else:
            self._force_full_redraw = False

        self.widget_count = self.widget_counter
        self.widget_counter = 0
        self.event = event
        self.cursor_x = 1
        self.cursor_y = 1

        self._event_is_mouse = isinstance(event, MouseClick)
        self._mouse_event = event if self._event_is_mouse else None

        # Clamp focus if widget count changed (dynamic UIs)
        if self.widget_count > 0 and self.active_id is not None:
            self.active_id %= self.widget_count
        elif self.widget_count == 0:
            self.active_id = None

    def end_frame(self):
        self.event = None

        # Logical frame height must be tracked independently from dirty writes,
        # because cached widgets may skip serial output but still be visible.
        frame_bottom = self.cursor_y - 1
        if frame_bottom < 0:
            frame_bottom = 0

        clear_from_y = None
        if frame_bottom < self._last_frame_bottom:
            clear_from_y = frame_bottom + 1

        self.buffer.flush(clear_from_y=clear_from_y, force=self._force_full_redraw)
        self._last_frame_bottom = frame_bottom
        self._force_full_redraw = False

    def request_full_redraw(self):
        # Current frame: redraw any cached widgets not rendered yet.
        self._force_full_redraw = True
        # Next frame: ensures redraw also works when requested late.
        self._force_full_redraw_next = True

    @micropython.native
    def register_focusable(self):
        w_id = self.widget_counter
        self.widget_counter += 1
        if self.active_id is None and self.widget_count > 0:
            self.active_id = 0
        is_focused = (w_id == self.active_id)
        return w_id, is_focused


class UI:
    # -- layout helpers -------------------------------------------------
    @micropython.native
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
    @micropython.native
    @staticmethod
    def clickable(ctx: UIContext, x: int, y: int, width: int, height: int = 1):
        """
        Lowest-level interactable primitive.
        Returns (is_focused, activated_this_frame).
        """
        w_id, is_focused = ctx.register_focusable()
        activated = False

        # Keyboard activation
        if is_focused and ctx.event == Key.ENTER:
            activated = True
            ctx.event = None

        # Mouse activation + hit-test
        elif ctx._event_is_mouse and ctx.event is not None and ctx._mouse_event is not None:
            m = ctx._mouse_event
            if m.action == "PRESS" and m.button == "LEFT":
                mx = m.x
                my = m.y
                if x <= mx < x + width and y <= my < y + height:
                    ctx.active_id = w_id
                    is_focused = True
                    activated = True
                    ctx.event = None
                    ctx._event_is_mouse = False
                    ctx._mouse_event = None

        return is_focused, activated

    # -- non-interactive ------------------------------------------------
    @staticmethod
    def label(ctx: UIContext, text: str, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        cached = ctx.cache_get(("label", text))
        if cached is None:
            cached = text
            ctx.cache_store(("label", text), cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        ctx.cursor_y += 1

    @staticmethod
    def clear_line(ctx: UIContext, y=None):
        UI._resolve_pos(ctx, None, y)
        # clear_line is intentionally not cached; it is a side-effect op.
        ctx.buffer.add_at(1, ctx.cursor_y, "")

    @staticmethod
    def divider(ctx: UIContext, width: int = 34, char: str = "─", x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        params = ("divider", width, char)
        cached = ctx.cache_get(params)
        if cached is None:
            cached = f"{Term.DIM}{char * width}{Term.RESET}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        ctx.cursor_y += 1

    @staticmethod
    def badge(ctx: UIContext, label: str, value: str, color=Term.GREEN, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        params = ("badge", label, value, color)
        cached = ctx.cache_get(params)
        if cached is None:
            cached = (
                f"{Term.DIM}[{Term.RESET}{label}: "
                f"{color}{Term.BOLD}{value}{Term.RESET}{Term.DIM}]{Term.RESET}"
            )
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        ctx.cursor_y += 1

    @staticmethod
    def input(ctx: UIContext, value: str, label="", width=20, x=None, y=None):
        UI._resolve_pos(ctx, x, y)
        is_focused, _ = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        if is_focused:
            ev = ctx.event
            if isinstance(ev, str) and len(ev) == 1 and 32 <= ord(ev) < 127:
                value += ev
                ctx.event = None
            elif ev == Key.BACKSPACE:
                value = value[:-1]
                ctx.event = None

        params = ("input", label, value, width, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            prefix = label + ": " if label else ""
            suffix = "_" if is_focused else ""
            pad = width - len(value) - len(suffix)
            if pad > 0:
                suffix += " " * pad

            focus_style = Term.BG_CYAN + Term.BLACK if is_focused else ""
            cached = f"{prefix}{Term.UNDERLINE}{focus_style}{value}{suffix}{Term.RESET}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

        ctx.cursor_y += 1
        return value

    @staticmethod
    def gauge(ctx: UIContext, label: str, value: int, max_val: int,
              width: int = 20, x=None, y=None):
        UI._resolve_pos(ctx, x, y)

        params = ("gauge", label, value, max_val, width)
        cached = ctx.cache_get(params)
        if cached is None:
            ratio = max(0.0, min(1.0, value / max_val)) if max_val else 0.0
            filled = int(width * ratio)
            empty = width - filled
            bar = "█" * filled + "░" * empty
            pct = f"{int(ratio * 100):>3}%"
            cached = f"{label:<12} {Term.CYAN}{bar}{Term.RESET} {pct}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

        ctx.cursor_y += 1

    # -- interactive ----------------------------------------------------
    @staticmethod
    def button(ctx: UIContext, label: str, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        width = len(label) + 4
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        params = ("button", label, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            bg = Term.BG_BLUE if is_focused else ""
            cached = f"{bg}[ {label} ]{Term.RESET}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

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
            mark = "X" if checked else " "
            text = f"[{mark}] {label}"

        params = ("checkbox", label, checked, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            bg = Term.BG_BLUE if is_focused else ""
            cached = f"{bg}{text}{Term.RESET}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

        ctx.cursor_y += 1
        return checked

    @staticmethod
    def toggle(ctx: UIContext, label: str, active: bool, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        width = len(label) + 10
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

        if activated:
            active = not active

        params = ("toggle", label, active, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            prefix = " > " if is_focused else "   "
            if active:
                status = f"{Term.BG_GREEN}{Term.BLACK} ON {Term.RESET}"
            else:
                status = f"{Term.BG_RED}{Term.WHITE} OFF {Term.RESET}"

            cached = f"{prefix}{label:<15} {status}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

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

        params = ("stepper", label, value, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            val_str = f"{value:02d}"
            prefix = " > " if is_focused else "   "
            if is_focused:
                val_render = f"{Term.BG_CYAN}{Term.BLACK}<{val_str}>{Term.RESET}"
            else:
                val_render = f" {val_str} "
            cached = f"{prefix}{label:<15} {val_render}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

        ctx.cursor_y += 1
        return value

    @staticmethod
    def slider(ctx: UIContext, label: str, value: int,
               min_val: int = 0, max_val: int = 100, width: int = 20,
               x=None, y=None) -> int:
        UI._resolve_pos(ctx, x, y)
        bar_visual = width + 2  # [....]
        value_w = len(str(max_val))
        total_w = 12 + 1 + bar_visual + 1 + value_w + 3

        is_focused, _ = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, total_w, 1)

        if is_focused:
            if ctx.event == Key.LEFT:
                value = max(min_val, value - 1)
                ctx.event = None
            elif ctx.event == Key.RIGHT:
                value = min(max_val, value + 1)
                ctx.event = None

        params = ("slider", label, value, min_val, max_val, width, is_focused)
        cached = ctx.cache_get(params)
        if cached is None:
            if max_val != min_val:
                ratio = (value - min_val) / (max_val - min_val)
            else:
                ratio = 0.0

            if ratio < 0.0:
                ratio = 0.0
            elif ratio > 1.0:
                ratio = 1.0

            filled = int(width * ratio)
            empty = width - filled
            bar = "█" * filled + " " * empty
            bar_str = f"[{bar}]"
            if is_focused:
                bar_str = f"{Term.BG_BLUE}{Term.WHITE}{bar_str}{Term.RESET}"

            cached = f"{' > ' if is_focused else '   '}{label:<12} {bar_str} {value}"
            ctx.cache_store(params, cached)
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)
        elif ctx._force_full_redraw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached)

        ctx.cursor_y += 1
        return value

    @staticmethod
    def card(ctx: UIContext, title: str, subtitle: str,
             width: int = 30, x=None, y=None) -> bool:
        UI._resolve_pos(ctx, x, y)
        is_focused, activated = UI.clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 3)

        params = ("card", title, subtitle, width, is_focused)
        cached = ctx.cache_get(params)
        should_draw = ctx._force_full_redraw

        if cached is None:
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

            cached = (
                f"{border}{top}{Term.RESET}",
                f"{border}{mid}{Term.RESET}",
                f"{border}{bot}{Term.RESET}",
            )
            ctx.cache_store(params, cached)
            should_draw = True

        if should_draw:
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, cached[0])
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1, cached[1])
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 2, cached[2])

        ctx.cursor_y += 3
        return activated

    @staticmethod
    def window(ctx: UIContext, lines: list[str],
               width: int = 30, x=None, y=None) -> None:
        UI._resolve_pos(ctx, x, y)

        lines_tuple = tuple(lines)
        params = ("window", width, lines_tuple)
        cached = ctx.cache_get(params)
        should_draw = ctx._force_full_redraw

        if cached is None:
            border = Term.BLUE
            inner_w = width - 2
            top = f"┌{'─' * inner_w}┐"
            bot = f"└{'─' * inner_w}┘"

            rendered = [f"{border}{top}{Term.RESET}"]
            for line in lines_tuple:
                rendered.append(f"{border}│{line.center(inner_w)}│{Term.RESET}")
            rendered.append(f"{border}{bot}{Term.RESET}")
            cached = tuple(rendered)
            ctx.cache_store(params, cached)
            should_draw = True

        if should_draw:
            for i, row in enumerate(cached):
                ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + i, row)

        ctx.cursor_y += len(lines_tuple) + 2
