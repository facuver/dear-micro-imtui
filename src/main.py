import asyncio
from dear_micro_imtui import App, UI, Term, Key
import machine
import neopixel
import time

# Feather RP2040 onboard NeoPixel is on GPIO 18
pixel = neopixel.NeoPixel(machine.Pin(16), 1)


class Dashboard(App):
    def __init__(self):
        super().__init__(max_fps=1000)
        self.power = False
        self.brightness = 40
        self.pixel = pixel = neopixel.NeoPixel(machine.Pin(16), 1)
        self.red =0
        self.green =0
        self.blue =0
        self.auto_update = True
        self.text1= "Placeholder"

    def on_ui(self):
        start_time = time.ticks_cpu()
        self.text1 = UI.label(self.ctx,f"test",x=5)
        end_time = time.ticks_cpu() - start_time
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)


        UI.label(self.ctx,f"{Term.DIM}   FPS : {1000//self.frame_rate}  Keys : {len(self.ctx.buff_cache.keys())} {Term.RESET} ",)
        UI.label(self.ctx,str(end_time) )
        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        for i in range(20):
            self.blue = UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)


    def turn_off(self,ctx,e):
        self.red,self.green,self.blue = 0,0,0
        self.pixel.write()
    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()
        self.keybindings.bind("o",  self.turn_off, help="off",phase="late")
        self.keybindings.bind(Key.ESCAPE,  self.turn_off, help="off",phase="late")

app = Dashboard()
app.run()
