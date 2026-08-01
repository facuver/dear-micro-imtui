from dear_micro_imgui import App, UI, Term, Key
import machine
import neopixel
import time

# Feather RP2040 onboard NeoPixel is on GPIO 18
pixel = neopixel.NeoPixel(machine.Pin(16), 1)


class Dashboard(App):
    def __init__(self):
        super().__init__(fps=40)
        self.power = False
        self.brightness = 40
        self.pixel = pixel = neopixel.NeoPixel(machine.Pin(16), 1)
        self.red =0
        self.green =0
        self.blue =0

    def on_ui(self):

        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10)
        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue = UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)


        if UI.button(self.ctx,"Off"):
            self.red,self.green,self.blue = 0,0,0
        self.pixel[0] = (self.red*25, self.green*25, self.blue*25)
        self.pixel.write()

    def turn_off(self,ctx,e):
        self.red,self.green,self.blue = 0,0,0
        self.pixel.write()
    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()
        self.keybindings.bind("o",  self.turn_off, help="off",phase="early")

app = Dashboard()
app.run()
