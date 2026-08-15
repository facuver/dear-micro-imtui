from claude import main
main()
raise
import machine
from dear_micro_imtui import App, UI, Term, Key
import micropython
import network


import network
import time

try:
    import machine
    _MP = True
except ImportError:
    _MP = False


class Network:
    """MicroPython WiFi helper: connect, monitor, and report status."""

    def __init__(self, ssid, password, hostname=None, timeout_s=15):
        self.ssid = ssid
        self.password = password
        self.timeout_s = timeout_s
        self.sta = network.WLAN(network.STA_IF)
        if hostname and hasattr(self.sta, "config"):
            try:
                self.sta.config(hostname=hostname)
            except Exception:
                pass

    # -- connection -----------------------------------------------------
    def connect(self):
        """Connect to the configured AP. Returns True on success."""
        if self.is_connected():
            return True
        self.sta.active(True)
        self.sta.connect(self.ssid, self.password)
        deadline = time.ticks_ms() + self.timeout_s * 1000
        while not self.is_connected():
            if time.ticks_diff(time.ticks_ms(), deadline) > 0:
                return False
            time.sleep_ms(250)
        return True

    def disconnect(self):
        if self.sta.isconnected():
            self.sta.disconnect()

    def deinit(self):
        self.disconnect()
        self.sta.active(False)

    # -- status ---------------------------------------------------------
    def is_connected(self):
        return self.sta.isconnected()

    def status(self):
        """Return a dict describing the current link state."""
        return {
            "active": self.sta.active(),
            "connected": self.is_connected(),
            "ifconfig": self.sta.ifconfig() if self.is_connected() else None,
            "rssi": self.rssi(),
        }

    def ip(self):
        if self.is_connected():
            return self.sta.ifconfig()[0]
        return None

    def rssi(self):
        if self.is_connected() and hasattr(self.sta, "status"):
            try:
                return self.sta.status("rssi")
            except Exception:
                return None
        return None

    # -- scanning -------------------------------------------------------
    def scan(self):
        """Return a list of (ssid, bssid, channel, rssi, auth) tuples."""
        self.sta.active(True)
        return self.sta.scan()

    # -- blocking wait --------------------------------------------------
    def wait_connected(self, timeout_s=None):
        """Block until connected or timeout. Returns True on success."""
        timeout_s = timeout_s or self.timeout_s
        deadline = time.ticks_ms() + timeout_s * 1000
        while not self.is_connected():
            if time.ticks_diff(time.ticks_ms(), deadline) > 0:
                return False
            time.sleep_ms(250)
        return True


class Dashboard(App):
    def __init__(self):
        super().__init__(max_fps=200)
        self.tabs = ("NETWORK","BLE","GPIO","MEMORY")
        self.selected_tab = 0
        self.network = Network("","")
        self.available = []
    def on_ui(self):
        UI.label(self.ctx,f"ESP32-S3 Dashboard   {Term.DIM} FPS: {1000//max(1,self.frame_rate)}{Term.RESET}")
        UI.label(self.ctx,f"""╔══════════╦══════════╦══════════╗\n║  Tab 1   ║  Tab 2   ║  Tab 3   ║\n╚══════════╝          ╚══════════╝ """)


        self.selected_tab = UI.tabs(self.ctx, self.tabs,self.selected_tab,y=6)
        if self.selected_tab == 0:
            if self.available:
                UI.select(self.ctx,"SSID",tuple([s[0].decode() for s in self.available]),0)
                self.network.password = UI.input(self.ctx,"PASS",self.network.password,)

            if UI.button(self.ctx, "Scan" ):
                self.available= self.network.scan()

        elif self.selected_tab ==3:
            import gc
            UI.gauge(self.ctx,"RAM",gc.mem_alloc(),max_val=gc.mem_free()+gc.mem_alloc() )
            if UI.button(self.ctx,"MAKE HUGE ALLOCU"):
                var = bytearray(600000)
            if UI.button(self.ctx,"GC COLLECT", x=30,y=-1):
                gc.collect()
    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()


app = Dashboard()
app.run()
