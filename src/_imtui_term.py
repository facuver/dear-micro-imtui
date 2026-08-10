import random
import sys


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

    @classmethod
    def save_pos(cls):
        sys.stdout.write("\x1b[s")

    @classmethod
    def restore_pos(cls):
        sys.stdout.write("\x1b[u")

    @classmethod
    def move_pos(cls,x,y):
        sys.stdout.write(f"\x1b[{y};{x}H")

    @classmethod
    def get_pos(cls, timeout=100):
        import time
        import select

        sys.stdout.write("\x1b[6n")
        poll = select.poll()
        poll.register(sys.stdin, select.POLLIN)

        r = ""
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while True:
            remaining = time.ticks_diff(deadline, time.ticks_ms())
            if remaining <= 0:
                return None
            if not poll.poll(remaining):
                return None
            c = sys.stdin.read(1)
            if not c:
                return None
            r += c
            if c == "R":
                break
        try:
            y = int(r[r.find("[")+1:r.find(";")])
            x = int(r[r.find(";")+1:r.find("R")])
        except Exception as e:
            print(e)
            return None
        return x,y


    @classmethod
    def get_size(cls):
        cls.save_pos()
        cls.move_pos(999,999)
        x,y = cls.get_pos()
        cls.restore_pos()
        return x,y


