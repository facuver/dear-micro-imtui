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
    def flush(self, clear_from_y=None):
        """
        Flush queued draw ops.

        If `clear_from_y` is provided, clear from that row to end-of-screen.
        This is used when the new frame is shorter than the previous one.
        """
        if not self.count and clear_from_y is None:
            return

        chunks = []
        for i in range(self.count):
            item = self.parts[i]
            if item is None:
                continue
            x, y, text = item
            chunks.append(f"\x1b[{y};{x}H{text}\x1b[K")

        if clear_from_y is not None:
            chunks.append(f"\x1b[{clear_from_y};1H\x1b[J")

        if chunks:
            sys.stdout.write("".join(chunks))

        # sys.stdout.flush()
        self.count = 0
