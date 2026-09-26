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

## Show system status

```sh
adafruitdisplay-stats                        # address, load, memory, disk
adafruitdisplay-stats --preview stats.png    # render one frame to a file
```

## Library

```python
from adafruitdisplay import ON, Display, TextFrame

with Display.open() as display:
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
