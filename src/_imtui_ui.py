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
        "buff_cache",
        "text_cache",
        "_last_frame_bottom",
        "_force_full_redraw",
        "_force_full_redraw_next",
        "_event_is_mouse",
        "_mouse_event",
    )

    def __init__(self):
        self.active_id = None
        self.widget_counter = 0
        self.widget_count = 0
        self.buffer = Buffer()
        self.event = None
        self.cursor_x = 1
        self.cursor_y = 1
        self.dirty_lines = set()
        # (x, y) -> content_hash
        self.buff_cache = {}

        self._last_frame_bottom = 0
        self._event_is_mouse = False
        self._mouse_event = None

    def begin_frame(self, event):
        self.widget_count = self.widget_counter
        self.widget_counter = 0
        self.event = event
        self.cursor_x = 1
        self.cursor_y = 1

        if self.widget_count > 0 and self.active_id is not None:
            self.active_id %= self.widget_count
        elif self.widget_count == 0:
            self.active_id = None

    def end_frame(self):
        self.event = None

        frame_bottom = self.cursor_y - 1
        if frame_bottom < 0:
            frame_bottom = 0

        clear_from_y = None
        if frame_bottom < self._last_frame_bottom:
            clear_from_y = frame_bottom + 1

        self.buffer.flush(clear_from_y=clear_from_y)
        self._last_frame_bottom = frame_bottom
        self.dirty_lines.clear()

    def clear_cache(self):
        self.buff_cache.clear()

    @micropython.native
    def register_focusable(self):
        w_id = self.widget_counter
        self.widget_counter += 1
        if self.active_id is None and self.widget_count > 0:
            self.active_id = 0
        return w_id, (w_id == self.active_id)


@micropython.native
def _resolve_pos(ctx: UIContext, x, y):
    if x is not None:
        ctx.cursor_x = x
    if y is not None:
        if y < 0:
            ctx.cursor_y += y
        else:
            ctx.cursor_y = y


def _cache_hit(ctx: UIContext, content_hash):
    key = (ctx.cursor_x, ctx.cursor_y)
    return (ctx.buff_cache.get(key, None) == content_hash) and ctx.cursor_y not in ctx.dirty_lines


def _cache_store(ctx: UIContext, content_hash):
    key = (ctx.cursor_x, ctx.cursor_y)
    ctx.dirty_lines.add(ctx.cursor_y)
    ctx.buff_cache[key] = content_hash


@micropython.native
def clickable(ctx: UIContext, x: int, y: int, width: int, height: int = 1):
    w_id, is_focused = ctx.register_focusable()
    activated = False

    if is_focused and ctx.event == Key.ENTER:
        activated = True
        ctx.event = None
    elif isinstance(ctx.event, MouseClick):
        if ctx.event.action == "PRESS" and ctx.event.button == "LEFT":
            mx = ctx.event.x
            my = ctx.event.y
            if x <= mx < x + width and y <= my < y + height:
                ctx.active_id = w_id
                is_focused = True
                activated = True
                ctx.event = None

    return is_focused, activated


# -- non-interactive ------------------------------------------------

def label(ctx: UIContext, text: str, x=None, y=None):
    _resolve_pos(ctx, x, y)

    content_hash = hash(text)
    if not _cache_hit(ctx, content_hash):
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1


def clear_line(ctx: UIContext, y=None):
    _resolve_pos(ctx, None, y)
    line_y = ctx.cursor_y

    # Invalidate cache entries on the cleared terminal row.
    stale = []
    for key in ctx.buff_cache.keys():
        if key[1] == line_y:
            stale.append(key)
    for key in stale:
        del ctx.buff_cache[key]

    ctx.buffer.add_at(1, line_y, "")


def divider(ctx: UIContext, width: int = 34, char: str = "─", x=None, y=None):
    _resolve_pos(ctx, x, y)

    content_hash = hash((char, width))
    if not _cache_hit(ctx, content_hash):
        text = f"{Term.DIM}{char * width}{Term.RESET}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1


def badge(ctx: UIContext, label: str, value: str, color=Term.GREEN, x=None, y=None):
    _resolve_pos(ctx, x, y)

    content_hash = hash((label, value, color))
    if not _cache_hit(ctx, content_hash):
        text = (
            f"{Term.DIM}[{Term.RESET}{label}: "
            f"{color}{Term.BOLD}{value}{Term.RESET}{Term.DIM}]{Term.RESET}"
        )
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1

def tabs(ctx:UIContext,options:tuple,selected:int,x=None,y=None):
    _resolve_pos(ctx, x, y)
    content_hash = hash((options, selected))
    #┌┐│
    is_focused,is_activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y,80, 1)


    header = f"{Term.UNDERLINE}│ {" │".join(options[:selected])} │{Term.RESET}{Term.BG_MAGENTA if is_focused else ""} {options[selected]} {Term.RESET + Term.UNDERLINE}│ {" │ ".join(options[selected+1:])}│{Term.RESET}"
    if is_focused:
        if ctx.event == Key.LEFT:
            selected -=1
        elif ctx.event == Key.RIGHT:
            selected +=1
        selected %= len(options)

    ctx.buffer.add_at(ctx.cursor_x,ctx.cursor_y,header)
    ctx.cursor_y+=1
    return selected


def gauge(ctx: UIContext, label: str, value: int, max_val: int,
          width: int = 20, x=None, y=None):
    _resolve_pos(ctx, x, y)

    content_hash = hash((label, value, max_val, width))
    if not _cache_hit(ctx, content_hash):
        ratio = max(0.0, min(1.0, value / max_val)) if max_val else 0.0
        filled = int(width * ratio)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        pct = f"{int(ratio * 100):>3}%"
        text = f"{label:<12} {Term.CYAN}{bar}{Term.RESET} {pct}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1


# -- interactive ----------------------------------------------------
def input(ctx: UIContext, value: str, label="", width=20, x=None, y=None):
    _resolve_pos(ctx, x, y)

    prefix_len = len(label) + 2 if label else 0
    is_focused, _ = clickable(ctx, ctx.cursor_x, ctx.cursor_y, prefix_len + width, 1)

    if is_focused:
        ev = ctx.event
        if isinstance(ev, str) and len(ev) == 1 and 32 <= ord(ev) < 127:
            value += ev
            ctx.event = None
        elif ev == Key.BACKSPACE:
            value = value[:-1]
            ctx.event = None

    content_hash = hash((label, value, width, is_focused))
    if not _cache_hit(ctx, content_hash):
        prefix = label + ": " if label else ""
        suffix = "_" if is_focused else ""
        pad = width - len(value) - len(suffix)
        if pad > 0:
            suffix += " " * pad

        focus_style = Term.BG_CYAN + Term.BLACK if is_focused else ""
        text = f"{prefix}{Term.UNDERLINE}{focus_style}{value}{suffix}{Term.RESET}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1
    return value


def button(ctx: UIContext, label: str, x=None, y=None) -> bool:
    _resolve_pos(ctx, x, y)

    width = len(label) + 4
    is_focused, activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

    content_hash = hash((label, is_focused))
    if not _cache_hit(ctx, content_hash):
        bg = Term.BG_BLUE if is_focused else ""
        text = f"{bg}[ {label} ]{Term.RESET}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1
    return activated


def checkbox(ctx: UIContext, label: str, checked: bool, x=None, y=None) -> bool:
    _resolve_pos(ctx, x, y)

    width = len(label) + 4
    is_focused, activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

    if activated:
        checked = not checked

    content_hash = hash((label, checked, is_focused))
    if not _cache_hit(ctx, content_hash) :
        mark = "X" if checked else " "
        text = f"[{mark}] {label}"
        bg = Term.BG_BLUE if is_focused else ""
        out = f"{bg}{text}{Term.RESET}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, out)

    ctx.cursor_y += 1
    return checked


def toggle(ctx: UIContext, label: str, active: bool, x=None, y=None) -> bool:
    _resolve_pos(ctx, x, y)

    width = len(label) + 10
    is_focused, activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

    if activated:
        active = not active

    content_hash = hash((label, active, is_focused))
    if not _cache_hit(ctx, content_hash):
        prefix = " > " if is_focused else "   "
        if active:
            status = f"{Term.BG_GREEN}{Term.BLACK} ON {Term.RESET}"
        else:
            status = f"{Term.BG_RED}{Term.WHITE} OFF {Term.RESET}"

        text = f"{prefix}{label:<15} {status}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1
    return active


def number_stepper(ctx: UIContext, label: str, value: int,
                   min_val: int = 0, max_val: int = 99, step: int = 1,
                   x=None, y=None) -> int:
    _resolve_pos(ctx, x, y)

    width = len(label) + 12
    is_focused, activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 1)

    if is_focused:
        if ctx.event == Key.LEFT:
            value = max(min_val, value - step)
            ctx.event = None
        elif ctx.event == Key.RIGHT or activated:
            value = min(max_val, value + step)
            ctx.event = None

    content_hash = hash((label, value, min_val, max_val, step, is_focused))
    if not _cache_hit(ctx, content_hash):
        val_str = f"{value:02d}"
        prefix = " > " if is_focused else "   "
        if is_focused:
            val_render = f"{Term.BG_CYAN}{Term.BLACK}<{val_str}>{Term.RESET}"
        else:
            val_render = f" {val_str} "

        text = f"{prefix}{label:<15} {val_render}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1
    return value


@micropython.native
def select(ctx:UIContext,lable:str,options:tuple=(),value=0,hint=True,x=None,y=None):
    _resolve_pos(ctx, x, y)
    is_focused, clicked = clickable(ctx, ctx.cursor_x, ctx.cursor_y, 20, 1)

    if is_focused:

        if ctx.event == Key.LEFT:
            value -=1
            ctx.event = None
        elif ctx.event == Key.RIGHT or clicked:
            value+=1
            ctx.event = None


        value %=len(options)


    content_hash = hash((label,options,value,is_focused))
    if not _cache_hit(ctx, content_hash):
        _cache_store(ctx, content_hash)



        t =  f"{Term.BG_CYAN}<{options[value]}>{Term.RESET}  {Term.DIM}{options if hint else ""}{Term.RESET}"  if is_focused else  f"{options[value]}"
        ctx.buffer.add_at(ctx.cursor_x,ctx.cursor_y,f"{lable}: {t}")

    ctx.cursor_y +=1
    return value






@micropython.native
def slider(ctx: UIContext, label: str, value: int,
           min_val: int = 0, max_val: int = 100, width: int = 20,
           x=None, y=None) -> int:
    _resolve_pos(ctx, x, y)
    bar_visual = width + 2
    total_w = bar_visual + 20

    is_focused, _ = clickable(ctx, ctx.cursor_x, ctx.cursor_y, total_w, 1)

    if is_focused:
        if ctx.event == Key.LEFT:
            value = max(min_val, value - 1)
            ctx.event = None
        elif ctx.event == Key.RIGHT:
            value = min(max_val, value + 1)
            ctx.event = None

    content_hash = hash((label, value, min_val, max_val, width, is_focused))
    if not _cache_hit(ctx, content_hash):
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

        text = f"{' > ' if is_focused else '   '}{label:<12} {bar_str} {value}"
        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, text)

    ctx.cursor_y += 1
    return value


def card(ctx: UIContext, title: str, subtitle: str,
         width: int = 30, x=None, y=None) -> bool:
    _resolve_pos(ctx, x, y)

    is_focused, activated = clickable(ctx, ctx.cursor_x, ctx.cursor_y, width, 3)

    content_hash = hash((title, subtitle, width, is_focused))
    if not _cache_hit(ctx, content_hash):
        border = Term.GREEN if is_focused else Term.DIM

        inner = width - 4
        left = max(0, (inner - len(title)) // 2)
        right = max(0, inner - len(title) - left)
        top = f"┌{'─' * left} {title} {'─' * right}┐"

        mid_inner = width - 2
        mleft = max(0, (mid_inner - len(subtitle)) // 2)
        mright = max(0, mid_inner - len(subtitle) - mleft)
        mid = f"│{' ' * mleft}{subtitle}{' ' * mright}│"

        bot = f"└{'─' * (width - 2)}┘"

        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{border}{top}{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1, f"{border}{mid}{Term.RESET}")
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 2, f"{border}{bot}{Term.RESET}")

    ctx.cursor_y += 3
    return activated


def window(ctx: UIContext, lines: list[str],
           width: int = 30, x=None, y=None) -> None:
    _resolve_pos(ctx, x, y)

    line_count = len(lines)
    content_hash = hash((width, tuple(lines)))

    if not _cache_hit(ctx, content_hash):
        border = Term.BLUE
        inner_w = width - 2
        top = f"┌{'─' * inner_w}┐"
        bot = f"└{'─' * inner_w}┘"

        _cache_store(ctx, content_hash)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y, f"{border}{top}{Term.RESET}")
        for i, line in enumerate(lines):
            row = f"{border}│{line.center(inner_w)}│{Term.RESET}"
            ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1 + i, row)
        ctx.buffer.add_at(ctx.cursor_x, ctx.cursor_y + 1 + line_count, f"{border}{bot}{Term.RESET}")

    ctx.cursor_y += line_count + 2
