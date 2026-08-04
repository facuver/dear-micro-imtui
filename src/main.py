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
        # self.auto_update= UI.checkbox(self.ctx,"Auto-Update", self.auto_update ,x=5, y=2)

        UI.label(self.ctx,f"{Term.DIM} FPS : {self.frame_rate} {Term.RESET} ",x=20,y=1)

        self.text1 = UI.input(self.ctx,self.text1,label="Test",x=5, width=10)
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)

        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)

        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)

        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)

        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)
        self.red = UI.slider(self.ctx,"RED",self.red,min_val=0,max_val=10,x=2)

        self.green = UI.slider(self.ctx,"GREEN",self.green,min_val=0,max_val=10)
        self.blue= UI.slider(self.ctx,"BLUE",self.blue,min_val=0,max_val=10)

        # UI.label(self.ctx,f"{times}")


        if self.auto_update:
            self.pixel[0] = (self.red*25, self.green*25, self.blue*25)
            self.pixel.write()
        else:
            if UI.button(self.ctx,"Off"):
                self.red,self.green,self.blue = 0,0,0
                self.pixel[0] = (self.red*25, self.green*25, self.blue*25)
                self.pixel.write()

            if UI.button(self.ctx,"Update", x=10,y=-1):
                self.pixel[0] = (self.red*25, self.green*25, self.blue*25)
                self.pixel.write()
    def turn_off(self,ctx,e):
        self.red,self.green,self.blue = 0,0,0
        self.pixel.write()
    def _setup_default_keybindings(self):
        super()._setup_default_keybindings()
        self.keybindings.bind("o",  self.turn_off, help="off",phase="late")
        self.keybindings.bind(Key.ESCAPE,  self.turn_off, help="off",phase="late")

app = Dashboard()
app.run()
