import sys


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
