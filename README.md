# adafruitdisplay

Draw text and status screens on a small SSD1306 OLED, such as the
[Adafruit PiOLED][pioled] (128x32, I2C). It uses Adafruit's current
CircuitPython driver through Blinka, so it runs on current Raspberry Pi OS.

## Install

On the Pi, with I2C switched on (`sudo raspi-config`, Interface Options):

```sh
pip install 'adafruitdisplay[pi] @ git+https://github.com/drakkhen/python-adafruitdisplay.git'
```

Leave out `[pi]` on a computer without the display; everything except
`Display.open()` still works.

## Show screens

`oled-display` shows each screen for five seconds, in step with the clock so
several displays change together. While switched off it runs a screen saver
that moves the hostname around, so no pixel stays lit for long.

```sh
oled-display                                  # hostname/IP, then load/memory/disk/uptime
oled-display --control 0.0.0.0:5001 --on      # switch with GET /on and /off
oled-display --rotate 180 --contrast 128      # upside-down mount, dimmer
oled-display --preview screens/               # save each screen as a PNG and exit
```

`--title-font` and `--text-font` take a path to any TrueType font. Other
packages add screens through the `adafruitdisplay.screens` entry point group;
[pihole-status][pihole] adds a `pihole` screen, for example.

The `/`, `/on` and `/off` endpoints answer `{"status": "on"}` or
`{"status": "off"}`, which suits the homebridge-simple-http plugin.

## Dimming

An SSD1306 can lose its settings to a corrupted I2C transfer. The whole screen
goes over in one transfer, and if the byte that marks it as pixel data is
corrupted, the controller reads the pixels as commands. A mostly black screen
is mostly `0x00`, so a stray "set contrast" leaves the display dim until the
controller is set up again, which is why a reboot seemed to fix it. `Display`
now sends its settings again every five minutes and after any failed write,
without switching the display off.

## Library

```python
from adafruitdisplay import ON, Display, TextFrame

with Display.open(rotate=180) as display:
    frame = TextFrame(display)
    frame.add_line("Four lines of")
    frame.add_line("eight-pixel text")
    display.show(frame)

    big = TextFrame(display, font_size=32)
    big.clear(ON)
    big.center_text("42", fill=0)
    display.show(big)
```

The screen blanks when the `with` block ends. To lay out frames without the
hardware, pass a `PreviewDriver("frame.png")` to `Display` and every frame is
saved as an image.

Text uses the bundled Silkscreen pixel font by Jason Kottke, which is sharpest
at multiples of 8 pixels.

## License

The code is MIT licensed (see `LICENSE`). The Silkscreen fonts are
Copyright (c) 2001 Jason Kottke and licensed under the SIL Open Font License
1.1, included as `src/adafruitdisplay/fonts/OFL.txt`.

## Development

```sh
pip install -e '.[dev]'
ruff check . && ruff format --check .
pytest
```

[pioled]: https://www.adafruit.com/product/3527
[pihole]: https://github.com/drakkhen/pihole-status
