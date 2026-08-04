import sys
import micropython

class Buffer:
    def __init__(self, max_size=(80, 50)):
        # Preallocate the backing storage so appends never trigger a resize.
        self.capacity = max_size[0] * max_size[1]
        self.parts = [None] * self.capacity
        self.count = 0


    @micropython.native
    def add_at(self, x: int, y: int, text: str):
        """Queue a draw of text at (x,y); formatting happens at flush time."""
        if self.count < self.capacity:
            self.parts[self.count] = (x, y, text)
            self.count += 1
        else:
            # Overflow beyond the preallocated capacity.
            self.parts.append((x, y, text))
            self.capacity += 1
            self.count += 1
    @micropython.native
    def flush(self):
        if not self.count:
            return
        payload = "".join(
            f"\x1b[{y};{x}H{text}\x1b[K"
            for x, y, text in self.parts[: self.count]
        )
        sys.stdout.write("\x1b[H" + payload + "\x1b[J")
        # sys.stdout.flush()
        self.count = 0
