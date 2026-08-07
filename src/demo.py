from dear_micro_imtui import App, UI, Term, Key
import time

class Dashboard(App):
    def __init__(self):
        super().__init__(max_fps=10)
        self.power = False
        self.brightness = 40
        self.volume = 60
        self.mode = 0
        self.modes = ["ECO", "BALANCED", "PERFORMANCE", "TURBO"]
        self.alert_count = 0
        self.show_help= False

    def on_ui(self):

        if self.show_help:
            UI.window(self.ctx, [f"{key}: {help}" for key,help in self.keybindings._help.items()], y=2,x=2 )
            return



        # -------- Header --------
        UI.label(self.ctx, f"{Term.BOLD}  MicroPython System Controller  {Term.RESET}", x=2, y=1)
        UI.divider(self.ctx, width=50, x=2)

        # -------- Status badges --------
        net_status = "ONLINE" if self.power else "OFFLINE"
        net_color = Term.GREEN + Term.BOLD if self.power else Term.RED
        UI.badge(self.ctx, "NET", net_status, color=net_color, x=2)
        UI.badge(self.ctx, "MODE", self.modes[self.mode], color=Term.YELLOW, x=24 ,y=3)

        UI.divider(self.ctx, width=50, x=2)

        # -------- Controls --------
        self.power = UI.toggle(self.ctx, "Main Power", self.power, x=2)

        if self.power:
            self.mode = UI.number_stepper(
                self.ctx, "Op Mode", self.mode,
                min_val=0, max_val=len(self.modes) - 1, step=1, x=2
            )
            self.mode = max(0, min(len(self.modes) - 1, self.mode))

            self.brightness = UI.slider(
                self.ctx, "Brightness", self.brightness, 0, 100, width=18, x=2
            )
            self.volume = UI.slider(
                self.ctx, "Volume", self.volume, 0, 100, width=18, x=2
            )

            if UI.button(self.ctx, "Trigger Alert", x=2):
                self.alert_count += 1
            # UI.clear_line(self.ctx)
            if UI.button(self.ctx, "Reset Alert", y=-1 ,x=22):
                self.alert_count = 0

        UI.divider(self.ctx, width=50, x=2)

        # -------- Gauges --------
        if self.power:
            UI.gauge(self.ctx, "CPU Load", 30 + self.volume // 3, 100, width=24, x=2)
            UI.gauge(self.ctx, "Temp", 45 + self.brightness // 5, 100, width=24, x=2)
            self.brightness -=1
            self.brightness %=100

        # -------- Card --------

        card_sub = f"Alerts: {self.alert_count} | Frame time: {1000//self.frame_rate }ms"
        UI.card(self.ctx, "SYSTEM", card_sub, width=32, x=2)

        UI.divider(self.ctx, width=50, x=2)

        # -------- Footer --------
        UI.label(self.ctx,
                 f"{Term.DIM}UP/DOWN: navigate  |  ENTER/SPACE/MOUSE: activate{Term.RESET}", x=2)
        UI.label(self.ctx,
                 f"{Term.DIM}LEFT/RIGHT: edit values  |  ESC: exit{Term.RESET}", x=2)


        # Exit on ESC
        if self.ctx.event == Key.ESCAPE:
            raise SystemExit


    def toggle_help(self,ctx,e):
        self.show_help = not self.show_help

    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()
        self.keybindings.bind("h",  self.toggle_help, help="help",phase="early")

    def _on_escape(self, ctx, event):
        # e.g., close a modal, defocus, etc.
        ctx.active_id = None
        return True

# Run it
app = Dashboard()
app.run()
