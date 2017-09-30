#!/usr/bin/env python
# -*- coding: utf-8 -*-
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import os
import signal
import subprocess
import sys

def font_dir():
    module_path = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(module_path, 'fonts')


class FrameBase:
    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height

        # First define some constants to allow easy resizing of shapes.
        padding = -2
        self.top = padding
        self.bottom = self.height - padding

        # Create blank image for drawing.
        # Make sure to create image with mode '1' for 1-bit color.
        self.image = Image.new('1', (self.width, self.height))
        # Get drawing object to draw on image.
        self.draw = ImageDraw.Draw(self.image)

    def clear(self, fill=0):
        # Draw a black filled box to clear the image.
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=fill)


class TextFrame(FrameBase):
    def __init__(self, display):
        FrameBase.__init__(self, display)

        self.line = 0
        default_font = os.path.join(font_dir(), 'slkscr.ttf')
        self.set_font(default_font, 8)

    def set_font(self, font_path, size):
        # Load nice silkscreen font, by default
        self.font = ImageFont.truetype(font_path, size)
        self.font_size = size

    def clear(self, fill=0):
        FrameBase.clear(self, fill)
        self.line = 0

    def center_text(self, s, fill="white"):
        w, h = self.draw.textsize(s, font=self.font)
        left = (self.width - w) / 2
        top = self.top + (self.height - h) / 2
        self.draw.text((left, top), s, font=self.font, fill=fill)

    def add_line(self, s, fill="white"):
        self.draw.text((0, self.top + self.line * self.font_size), s, font=self.font, fill=fill)
        self.line += 1

    def shell(self, cmd):
        res = subprocess.check_output(cmd, shell=True)
        return res


class OsStatusFrame(TextFrame):
    def update(self):
        ip_addr = self.shell("hostname -I | cut -d\' \' -f1").rstrip()
        hostname = self.shell("hostname -s").rstrip()
        load = self.shell("top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'")
        temp = self.shell("vcgencmd measure_temp").split("=")[-1].replace("'", u'°')
        mem = self.shell("free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'")
        disk = self.shell("df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'")

        self.clear()
        self.add_line("IP: %s (%s)" % (ip_addr, hostname))
        self.add_line("%s (%s)" % (load, temp))
        self.add_line(mem)
        self.add_line(disk)


class AdaFruitDisplay:
    def __init__(self):
        # 128x32 display with hardware I2C:
        self.disp = Adafruit_SSD1306.SSD1306_128_32(rst=None)

        self.width = self.disp.width
        self.height = self.disp.height

        # Initialize library.
        self.disp.begin()

        self.clear()

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signal, frame):
        self.clear()
        sys.exit(0)

    def clear(self):
        # Clear display.
        self.disp.clear()
        self.disp.display()

    def display_frame(self, frame):
        self.disp.image(frame.image)
        self.disp.display()
