import sys
import micropython


class Buffer:
    __slots__ = ("capacity", "parts", "count", "_last_frame")

    def __init__(self, max_size=(80, 50)):
        # Preallocate the backing storage so appends never trigger a resize.
        self.capacity = max_size[0] * max_size[1]
        self.parts = [None] * self.capacity
        self.count = 0
        # packed_key -> last rendered text at that position
        self._last_frame = {}

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
    def flush(self, clear_from_y=None, force=False):
        """
        Flush queued draw ops.

        - If `force` is False, unchanged (x,y,text) draws are skipped.
        - If `clear_from_y` is provided, clear from that row to end-of-screen.
        """
        if not self.count and clear_from_y is None:
            return

        chunks = []
        last = self._last_frame

        if self.count:
            final_index = {}

            # Keep only the last write for each cursor position this frame.
            for i in range(self.count):
                item = self.parts[i]
                if item is None:
                    continue
                x, y, _ = item
                final_index[(y << 16) | x] = i

            for i in range(self.count):
                item = self.parts[i]
                if item is None:
                    continue

                x, y, text = item
                key = (y << 16) | x

                # Superseded by a later write at the same position.
                if final_index.get(key) != i:
                    continue

                if force or last.get(key) != text:
                    chunks.append(f"\x1b[{y};{x}H{text}\x1b[K")

                last[key] = text

            # Release references for GC friendliness.
            for i in range(self.count):
                self.parts[i] = None

        if clear_from_y is not None:
            chunks.append(f"\x1b[{clear_from_y};1H\x1b[J")

            if last:
                to_delete = []
                for key in last:
                    if (key >> 16) >= clear_from_y:
                        to_delete.append(key)
                for key in to_delete:
                    del last[key]

        if chunks:
            sys.stdout.write("".join(chunks))

        # sys.stdout.flush()
        self.count = 0
