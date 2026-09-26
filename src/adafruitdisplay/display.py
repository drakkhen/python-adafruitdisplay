"""
The display itself, and the drivers that put pixels on it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PIL import Image

    from .frames import Frame

# The Adafruit PiOLED: a 128x32 SSD1306 at the default I2C address.
DEFAULT_WIDTH = 128
DEFAULT_HEIGHT = 32
DEFAULT_ADDRESS = 0x3C


class Driver(Protocol):
    """
    What :class:`Display` needs from a display driver.

    ``adafruit_ssd1306.SSD1306_I2C`` satisfies it, and so does
    :class:`PreviewDriver`.
    """

    width: int
    height: int

    def fill(self, color: int) -> None:
        """
        Set every pixel to ``color``: 0 for off, 1 for on.
        """
        ...

    def image(self, image: Image.Image) -> None:
        """
        Copy a 1-bit image into the frame buffer.
        """
        ...

    def show(self) -> None:
        """
        Send the frame buffer to the screen.
        """
        ...


class PreviewDriver:
    """
    A stand-in driver that saves each shown frame as a PNG file.

    Useful for laying out frames on a computer without the hardware.
    """

    def __init__(
        self, path: str | Path, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
    ) -> None:
        from PIL import Image

        self.path = Path(path)
        self.width = width
        self.height = height
        self.frame = Image.new("1", (width, height))

    def fill(self, color: int) -> None:
        """
        Set every pixel to ``color``: 0 for off, 1 for on.
        """
        self.frame.paste(color, (0, 0, self.width, self.height))

    def image(self, image: Image.Image) -> None:
        """
        Copy a 1-bit image into the frame buffer.
        """
        if image.size != (self.width, self.height):
            raise ValueError(f"image is {image.size}, display is {(self.width, self.height)}")
        self.frame = image.convert("1").copy()

    def show(self) -> None:
        """
        Write the frame buffer to :attr:`path`.
        """
        self.frame.save(self.path)


def open_ssd1306(
    width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, address: int = DEFAULT_ADDRESS
) -> Driver:
    """
    Open an SSD1306 OLED on the board's default I2C bus.

    Needs the ``pi`` extra: ``pip install 'adafruitdisplay[pi]'``.
    """
    import adafruit_ssd1306
    import board

    return adafruit_ssd1306.SSD1306_I2C(width, height, board.I2C(), addr=address)


class Display:
    """
    An OLED display that shows :class:`~adafruitdisplay.frames.Frame`s.

    Use it as a context manager to blank the screen when you're done::

        with Display.open() as display:
            display.show(frame)
    """

    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self.width = driver.width
        self.height = driver.height
        self.clear()

    @classmethod
    def open(
        cls,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        address: int = DEFAULT_ADDRESS,
    ) -> Display:
        """
        Open the SSD1306 on I2C. See :func:`open_ssd1306`.
        """
        return cls(open_ssd1306(width, height, address))

    def clear(self) -> None:
        """
        Blank the screen.
        """
        self.driver.fill(0)
        self.driver.show()

    def show(self, frame: Frame) -> None:
        """
        Put a frame on the screen.
        """
        self.driver.image(frame.image)
        self.driver.show()

    def __enter__(self) -> Display:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.clear()
