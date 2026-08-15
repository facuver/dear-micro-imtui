import io
import sys
import time
import micropython
from _imtui_term import Term


def timed_function(f, *args, **kwargs):
    def new_func(*args, **kwargs):
        t = time.ticks_us()
        result = f(*args, **kwargs)
        delta = time.ticks_diff(time.ticks_us(), t)
        print('Function {} Time = {:6.3f}us'.format("timeit=", delta))
        return result
    return new_func


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

class Style:
    DEFAULT  = 0
    RED      = 1
    GREEN    = 2
    YELLOW   = 3
    BLUE     = 4
    MAGENTA  = 5
    CYAN     = 6
    WHITE    = 7
    ERROR    = 8
    OK       = 9
    WARN     = 10
    SELECTED = 11
    HEADER   = 12
    DIM      = 13


# Kept minimal/additive on purpose -- flush_diff resets before applying a
# new style on any run transition, so entries here do NOT need their own
# leading "\x1b[0" reset. This is what keeps combo() below meaningful.
STYLE_TABLE = {
    Style.DEFAULT:  b"\x1b[0m",
    Style.RED:      b"\x1b[31m",
    Style.GREEN:    b"\x1b[32m",
    Style.YELLOW:   b"\x1b[33m",
    Style.BLUE:     b"\x1b[34m",
    Style.MAGENTA:  b"\x1b[35m",
    Style.CYAN:     b"\x1b[36m",
    Style.WHITE:    b"\x1b[37m",
    Style.ERROR:    b"\x1b[1;31m",
    Style.OK:       b"\x1b[32m",
    Style.WARN:     b"\x1b[1;33m",
    Style.SELECTED: b"\x1b[7m",
    Style.HEADER:   b"\x1b[1;4m",
    Style.DIM:      b"\x1b[2m",
}


def _check_style_table():
    names = [n for n in dir(Style) if not n.startswith('_')]
    ids = set(getattr(Style, n) for n in names)
    missing = ids - set(STYLE_TABLE.keys())
    assert not missing, "Style ids missing from STYLE_TABLE: %r" % missing


_check_style_table()

_combo_cache = {}


def combo(*style_ids):
    """Compose multiple styles into one new style id, cached so repeated
    calls with the same combination don't grow the table indefinitely."""
    key = tuple(sorted(style_ids))
    if key in _combo_cache:
        return _combo_cache[key]
    parts = []
    for sid in style_ids:
        seq = STYLE_TABLE[sid][2:-1]  # strip \x1b[ and trailing m
        parts.append(seq.decode())
    new_id = max(STYLE_TABLE.keys()) + 1
    STYLE_TABLE[new_id] = ("\x1b[" + ";".join(parts) + "m").encode()
    _combo_cache[key] = new_id
    return new_id


# ---------------------------------------------------------------------------
# Scratch -- allocation-free text building
# ---------------------------------------------------------------------------

class Scratch:
    """Reusable byte buffer for building text without per-frame allocation.

    Allocate once (outside your render loop), call .reset() each frame,
    then chain .text()/.int()/.float()/.char()/.pad() to build content,
    and pass .buffer() + len(scratch) into CharBuffer.write().
    """

    def __init__(self, capacity=64):
        self._buf = bytearray(capacity)
        self._cap = capacity
        self.pos = 0

    def reset(self):
        self.pos = 0
        return self

    def buffer(self):
        return self._buf

    def __len__(self):
        return self.pos

    def text(self, s):
        """Append literal text. Pass pre-encoded bytes to avoid allocation
        (e.g. module-level LABEL = b"Temp: " built once outside the loop);
        a str literal here will .encode() fresh each call."""
        if isinstance(s, str):
            s = s.encode()
        self.pos = self._append_bytes(self._buf, self.pos, s)
        return self

    def char(self, c):
        """Append a single ASCII char (int codepoint or 1-char str)."""
        if isinstance(c, str):
            c = ord(c)
        self.pos = self._append_byte(self._buf, self.pos, c)
        return self

    def int(self, value):
        """Append an integer as decimal ASCII, no allocation."""
        self.pos = self._append_int(self._buf, self.pos, value)
        return self

    def float(self, value, decimals=2):
        """Append a float with fixed decimal places.

        Float math itself is plain Python (viper has no float support);
        digit writing is delegated to the zero-alloc int writer.
        """
        neg = value < 0
        if neg:
            value = -value

        scale = 1
        for _ in range(decimals):
            scale *= 10
        scaled = int(value * scale + 0.5)  # manual round-half-up

        int_part = scaled // scale
        frac_part = scaled % scale

        if neg:
            self.pos = self._append_byte(self._buf, self.pos, 45)  # '-'
        self.pos = self._append_int(self._buf, self.pos, int_part)

        if decimals > 0:
            self.pos = self._append_byte(self._buf, self.pos, 46)  # '.'
            self.pos = self._append_int_padded(self._buf, self.pos, frac_part, decimals)

        return self

    def pad(self, n, fill=32):
        """Append n fill bytes (default: space). Useful for fixed-width
        columns or clearing leftover chars from a shorter previous value."""
        self.pos = self._append_fill(self._buf, self.pos, n, fill)
        return self

    # -- viper primitives (no allocation, no Python-level loops) -----

    @staticmethod
    @micropython.viper
    def _append_bytes(dst, pos: int, src) -> int:
        d = ptr8(dst)
        s = ptr8(src)
        n = int(len(src))
        i = 0
        while i < n:
            d[pos] = s[i]
            pos += 1
            i += 1
        return pos

    @staticmethod
    @micropython.viper
    def _append_byte(dst, pos: int, byte: int) -> int:
        d = ptr8(dst)
        d[pos] = byte
        return pos + 1

    @staticmethod
    @micropython.viper
    def _append_fill(dst, pos: int, n: int, val: int) -> int:
        d = ptr8(dst)
        i = 0
        while i < n:
            d[pos] = val
            pos += 1
            i += 1
        return pos

    @staticmethod
    @micropython.viper
    def _append_int(dst, pos: int, value: int) -> int:
        d = ptr8(dst)
        neg = value < 0
        if neg:
            value = -value
        if value == 0:
            d[pos] = 48
            return pos + 1
        tmp = value
        ndigits = 0
        while tmp > 0:
            tmp //= 10
            ndigits += 1
        if neg:
            d[pos] = 45  # '-'
            pos += 1
        end = pos + ndigits
        i = end - 1
        tmp = value
        while tmp > 0:
            d[i] = 48 + (tmp % 10)
            tmp //= 10
            i -= 1
        return end

    @staticmethod
    @micropython.viper
    def _append_int_padded(dst, pos: int, value: int, width: int) -> int:
        # zero-padded fixed-width int, needed for fractional digits
        d = ptr8(dst)
        i = pos + width - 1
        v = value
        w = 0
        while w < width:
            d[i] = 48 + (v % 10)
            v //= 10
            i -= 1
            w += 1
        return pos + width


# ---------------------------------------------------------------------------
# CharBuffer
# ---------------------------------------------------------------------------

class CharBuffer:
    # Class-level shared scratch buffer for flush_diff output. Every
    # CharBuffer that calls flush_diff() uses this same bytearray -- safe
    # because flushes are synchronous/sequential, never interleaved.
    # Reassignment (growth) MUST go through the class name, never `self.`,
    # or it silently shadows this with a private instance attribute.
    _outbuf = bytearray(256)

    def __init__(self, width=None, heigh=None):
        if width is None or heigh is None:
            self.width, self.heigh = Term.get_size()
        else:
            self.width = width
            self.heigh = heigh

        n = self.width * self.heigh
        self.buffer = bytearray(b" " * n)
        self.attrs = bytearray(n)  # 0 = Style.DEFAULT

    # -- clearing --------------------------------------------------------

    def clear(self):
        self._fill(self.buffer, len(self.buffer), 32)
        self._fill(self.attrs, len(self.attrs), 0)

    @staticmethod
    @micropython.viper
    def _fill(buffer, n: int, val: int):
        buf = ptr8(buffer)
        i = 0
        while i < n:
            buf[i] = val
            i += 1

    # -- writing -----------------------------------------------------

    def write(self, x, y, data, style=Style.DEFAULT, length=None):
        if isinstance(data, str):
            data = data.encode()
        if length is None:
            length = len(data)
        self._write(x, y, data, style, length)

    @micropython.viper
    def _write(self, x: int, y: int, data, style: int, length: int):
        width = int(self.width)
        heigh = int(self.heigh)
        if y < 0 or y >= heigh:
            return
        buf = ptr8(self.buffer)
        attrs = ptr8(self.attrs)
        src = ptr8(data)
        n = length
        base = y * width
        i = 0
        while i < n:
            dest_x = x + i
            if dest_x >= width:
                break
            if dest_x >= 0:
                buf[base + dest_x] = src[i]
                attrs[base + dest_x] = style
            i += 1

    # -- blitting ----------------------------------------------------

    @micropython.viper
    def blit(self, x: int, y: int, char_buffer):
        width = int(self.width)
        heigh = int(self.heigh)
        src_w = int(char_buffer.width)
        src_h = int(char_buffer.heigh)
        dst = ptr8(self.buffer)
        src = ptr8(char_buffer.buffer)
        dst_a = ptr8(self.attrs)
        src_a = ptr8(char_buffer.attrs)
        row = 0
        while row < src_h:
            dest_y = y + row
            if dest_y >= heigh:
                break
            if dest_y >= 0:
                dst_base = dest_y * width
                src_base = row * src_w
                col = 0
                while col < src_w:
                    dest_x = x + col
                    if dest_x >= width:
                        break
                    if dest_x >= 0:
                        dst[dst_base + dest_x] = src[src_base + col]
                        dst_a[dst_base + dest_x] = src_a[src_base + col]
                    col += 1
            row += 1

    # -- plain (non-diff) flush --------------------------------------

    def flush(self):
        out = io.StringIO()
        for row in range(self.heigh):
            base = row * self.width
            line = self.buffer[base:base + self.width]
            out.write(bytes(line).decode())
            out.write('\n')
        sys.stdout.write(out.getvalue())

    # -- diff flush ----------------------------------------------------

    @classmethod
    def _ensure_capacity(cls, needed):
        if needed > len(cls._outbuf):
            CharBuffer._outbuf = bytearray(needed + needed // 2)

    def flush_diff(self, other):
        worst_case = self.width * self.heigh * 17 + 8
        CharBuffer._ensure_capacity(worst_case)
        pos = self._flush_diff_core(other, CharBuffer._outbuf, STYLE_TABLE)
        if pos:
            sys.stdout.write(CharBuffer._outbuf[:pos])
        return pos

    @micropython.viper
    def _flush_diff_core(self, other, outbuf, style_table) -> int:
        width = int(self.width)
        heigh = int(self.heigh)
        buf = ptr8(self.buffer)
        obuf = ptr8(other.buffer)
        attrs = ptr8(self.attrs)
        oattrs = ptr8(other.attrs)
        out = ptr8(outbuf)
        pos = 0
        last_style = -1

        row = 0
        while row < heigh:
            base = row * width
            col = 0
            while col < width:
                i = base + col
                if buf[i] != obuf[i] or attrs[i] != oattrs[i]:
                    start = col
                    run_style = int(attrs[i])
                    while (col < width and
                           (buf[base + col] != obuf[base + col] or
                            attrs[base + col] != oattrs[base + col]) and
                           int(attrs[base + col]) == run_style):
                        col += 1

                    # move sequence: ESC [ {row+1} ; {col+1} H
                    out[pos] = 27; pos += 1
                    out[pos] = 91; pos += 1
                    pos = int(self._write_int(outbuf, pos, row + 1))
                    out[pos] = 59; pos += 1
                    pos = int(self._write_int(outbuf, pos, start + 1))
                    out[pos] = 72; pos += 1

                    # style transition: reset first, THEN apply, so styles
                    # never bleed into each other regardless of what ran
                    # before -- lets STYLE_TABLE entries stay minimal/
                    # composable (see combo()) instead of self-resetting.
                    if run_style != last_style:
                        if run_style != 0:
                            out[pos] = 27; pos += 1
                            out[pos] = 91; pos += 1
                            out[pos] = 48; pos += 1
                            out[pos] = 109; pos += 1
                        style_bytes = style_table[run_style]
                        sb = ptr8(style_bytes)
                        slen = int(len(style_bytes))
                        j = 0
                        while j < slen:
                            out[pos] = sb[j]
                            pos += 1
                            j += 1
                        last_style = run_style

                    # char run, direct pointer copy, no slice alloc
                    k = start
                    while k < col:
                        out[pos] = buf[base + k]
                        pos += 1
                        k += 1
                else:
                    col += 1
            row += 1

        if pos > 0:
            out[pos] = 27; out[pos + 1] = 91; out[pos + 2] = 48; out[pos + 3] = 109
            pos += 4

        return pos

    @staticmethod
    @micropython.viper
    def _write_int(outbuf, pos: int, value: int) -> int:
        out = ptr8(outbuf)
        if value == 0:
            out[pos] = 48
            return pos + 1
        tmp = value
        ndigits = 0
        while tmp > 0:
            tmp //= 10
            ndigits += 1
        end = pos + ndigits
        i = end - 1
        tmp = value
        while tmp > 0:
            out[i] = 48 + (tmp % 10)
            tmp //= 10
            i -= 1
        return end


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

def Ctx():
    Term.alt_buffer_enable()
    Term.clear()
    screen_front, screen_back = CharBuffer(40, 10), CharBuffer(40, 10)
    end_time = 0
    try:
        while True:
            yield screen_front, end_time
            start_time = time.ticks_us()
            screen_front.flush_diff(screen_back)
            end_time = time.ticks_us() - start_time
            screen_front, screen_back = screen_back, screen_front
            screen_front.clear()
    except KeyboardInterrupt:
        pass
        # Term.alt_buffer_disable()


def main():
    window = CharBuffer(20, 5)
    window.write(0, 0, "Title", Style.HEADER)
    window.write(0, 1, "Subtitle", Style.DIM)

    line = Scratch(32)

    for frame, (screen, dt) in enumerate(Ctx()):
        line.reset().text(b"Frame ").int(frame).text(b" dt=").int(dt).pad(3)
        screen.write(0, 0, line.buffer(), Style.OK, length=len(line))

        screen.blit(5, 1, window)
        screen.blit(25, 1, window)
