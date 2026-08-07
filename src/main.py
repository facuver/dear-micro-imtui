import machine
from dear_micro_imtui import App, UI, Term, Key
import micropython

class PinWidget:
    def __init__(self,pin):
        self.pin= pin
        self.mode=machine.Pin.IN

        self.modes =("IN","OUT","OPEN DRAIN")
    def __call__(self,ctx):
        self.mode= UI.select(ctx,f"Pin {self.pin}",self.modes,self.mode, hint=False , x=0)
        pin = machine.Pin(self.pin,self.mode,machine.Pin.PULL_DOWN)
        pin.value( UI.checkbox (ctx,"Value" , pin.value() , y=-1 ,x =30) )



class Dashboard(App):
    def __init__(self):
        super().__init__(max_fps=50)
        self.power = True
        self.brightness = 70
        self.volume = 45
        self.speed = 3
        self.mode = 1
        self.modes = ["SILENT", "NORMAL", "LOUD", "ULTRA"]
        self.dark_mode = True
        self.auto_save = False
        self.notifications = True
        self.alert_count = 0
        self.username = "user"
        self.show_help = False
        self.selected = 0
        self.p1 = PinWidget(1)
        self.p2 = PinWidget(2)

    def pin_widget(self, pin):

        p = machine.Pin(pin)
        modes = UI.select

    def on_ui(self):

        self.p1(self.ctx)
        self.p2(self.ctx)

        UI.label(
            self.ctx,
            f"{Term.DIM}FPS: {1000 // self.frame_rate}  "
            f"Widgets: {self.ctx.dirty_lines}{Term.RESET}",
            x=2,
        )

        if UI.button(self.ctx,"Helllo"):
            pass

        return

        # return
        if self.show_help:
            UI.window(
                self.ctx,
                [f"{key}: {desc}" for key, desc in self.keybindings._help.items()],
                width=40, x=2, y=2,
            )
            return

        # -------- Header --------
        UI.divider(self.ctx, width=40, x=2)

        # -------- Status badges --------
        pwr_color = Term.GREEN + Term.BOLD if self.power else Term.RED
        pwr_text = "ON" if self.power else "OFF"
        UI.badge(self.ctx, "PWR", pwr_text, color=pwr_color, x=2)
        UI.badge(self.ctx, "MODE", self.modes[self.mode], color=Term.YELLOW, x=20, y=-1)

        UI.divider(self.ctx, width=40, char="─", x=2)

        # -------- Toggles --------
        self.power = UI.toggle(self.ctx, "Power", self.power, x=2)
        self.dark_mode = UI.toggle(self.ctx, "Dark Mode", self.dark_mode, x=2)
        self.auto_save = UI.toggle(self.ctx, "Auto Save", self.auto_save, x=2)
        self.notifications = UI.toggle(self.ctx, "Notify", self.notifications, x=2)

        UI.divider(self.ctx, width=40, x=2)
        UI.input(self.ctx,"Password",label="Pass")
        # -------- Sliders & steppers --------
        if self.power:
            self.brightness = UI.slider(
                self.ctx, "Brightness", self.brightness, 0, 100, width=16, x=2
            )
            self.volume = UI.slider(
                self.ctx, "Volume", self.volume, 0, 100, width=16, x=2
            )
            self.speed = UI.number_stepper(
                self.ctx, "Speed", self.speed, min_val=1, max_val=10, step=1, x=2
            )
            self.mode = UI.number_stepper(
                self.ctx, "Mode", self.mode,
                min_val=0, max_val=len(self.modes) - 1, step=1, x=2
            )

            UI.divider(self.ctx, width=40, x=2)

            # -------- Buttons --------
            if UI.button(self.ctx, "Send Alert", x=2):
                self.alert_count += 1
            if UI.button(self.ctx, "Clear", x=18, y=-1):
                self.alert_count = 0

            UI.divider(self.ctx, width=40, x=2)

            # -------- Gauges --------
            load = min(100, 20 + self.brightness // 2 + self.volume // 3)
            temp = min(100, 30 + self.speed * 7)
            UI.gauge(self.ctx, "CPU Load", load, 100, width=20, x=2)
            UI.gauge(self.ctx, "Temp", temp, 100, width=20, x=2)

        UI.divider(self.ctx, width=40, x=2)

        # -------- Card --------
        sub = f"Alerts:{self.alert_count} Br:{self.brightness} Vol:{self.volume}"
        UI.card(self.ctx, "STATUS", sub, width=36, x=2)

        # -------- Footer --------
        UI.divider(self.ctx, width=40, x=2)
        UI.label(
            self.ctx,
            f"{Term.DIM}UP/DN:nav  L/R:edit  ENTER:act  h:help{Term.RESET}",
            x=2,
        )
        UI.label(
            self.ctx,
            f"{Term.DIM}FPS: {1000 // max(1, self.frame_rate)}  "
            f"Widgets: {len(self.ctx.buff_cache)}{Term.RESET}",
            x=2,
        )

    def toggle_help(self, ctx, e):
        self.show_help = not self.show_help
        return True

    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()
        self.keybindings.bind("h", self.toggle_help, help="help", phase="early")


app = Dashboard()
app.run()
