from _imtui_compat import _MP, asyncio, sleep_ms, ticks_diff, ticks_ms
from _imtui_input import InputReader, Key, KeyBindings
from _imtui_term import Term
from _imtui_ui import UIContext
import micropython

class App:
    def __init__(self, max_fps: int = 30):
        self.ctx = UIContext()
        self.reader = InputReader()
        self.fps_ms = int(1000 / max_fps)
        self.frame_rate = 0
        self.last_frame_time = ticks_ms()
        self._latest_event = None
        self._running = True

        self.keybindings = KeyBindings()
        self._setup_default_keybindings()
    @micropython.native
    async def _input_loop(self):
        while self._running:
            event = await self.reader.read()
            if event is not None:
                self._latest_event = event

    @micropython.native
    async def _ui_loop(self):
        while self._running:
            self.frame_rate = ticks_diff(ticks_ms(), self.last_frame_time)
            self.last_frame_time = ticks_ms()

            event = self._latest_event
            self._latest_event = None

            self.ctx.begin_frame(event)

            if self.ctx.event and self.keybindings.handle(self.ctx, self.ctx.event, "early"):
                self.ctx.event = None
            self.on_ui()

            # PHASE 2: Late bindings (navigation & overrides)
            if self.ctx.event and self.keybindings.handle(self.ctx, self.ctx.event, "late"):
                self.ctx.event = None

            self.ctx.end_frame()
            await sleep_ms(self.fps_ms)

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

    def _redraw(self, ctx=None, event=None):
        Term.clear()
        self.ctx.request_full_redraw()
        return True

    def _setup_default_keybindings(self):
        # Early: global shortcuts (run before widgets)
        self.keybindings.bind("r", self._redraw, help="REDRAW", phase="early")
        self.keybindings.bind("q", lambda ctx, e: self._quit() or True, help="QUIT", phase="late")

        # Late: default focus navigation (run only if widgets didn't eat the event)
        self.keybindings.bind(Key.UP, self._nav_prev, phase="late", help="NEXT")
        self.keybindings.bind(Key.DOWN, self._nav_next, phase="late", help="PREV")

    def _quit(self):
        self._running = False

    async def _run(self):
        await asyncio.gather(self._input_loop(), self._ui_loop())

    def run(self):
        Term.clear()
        Term.hide_cursor()
        self.reader.enable_mouse()
        try:
            asyncio.run(self._run())
        finally:
            self.reader.disable_mouse()
            Term.show_cursor()
            Term.clear()
            print("App exited.")
