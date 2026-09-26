"""
The display itself, and the drivers that put pixels on it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from PIL import Image

if TYPE_CHECKING:
    from .frames import Frame

log = logging.getLogger(__name__)

# The Adafruit PiOLED: a 128x32 SSD1306 at the default I2C address.
DEFAULT_WIDTH = 128
DEFAULT_HEIGHT = 32
DEFAULT_ADDRESS = 0x3C
DEFAULT_CONTRAST = 0xFF

# How often the controller's settings are sent again. See Display.
REFRESH_SECONDS = 300.0


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

    def write_cmd(self, cmd: int) -> None:
        """
        Send one command byte to the controller.
        """
        ...


class PreviewDriver:
    """
    A stand-in driver that saves each shown frame as a PNG file.

    Useful for laying out frames on a computer without the hardware.
    Commands sent to the controller are recorded in :attr:`commands`.
    """

    def __init__(
        self, path: str | Path, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
    ) -> None:
        self.path = Path(path)
        self.width = width
        self.height = height
        self.frame = Image.new("1", (width, height))
        self.commands: list[int] = []
        self.shows = 0

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
        self.shows += 1

    def write_cmd(self, cmd: int) -> None:
        """
        Record a command byte.
        """
        self.commands.append(cmd)


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


def settings_commands(
    driver: Driver, contrast: int = DEFAULT_CONTRAST, *, display_on: bool = True
) -> list[int]:
    """
    Return the SSD1306 setup commands, without turning the display off.

    These are the settings ``adafruit_ssd1306`` sends when it starts,
    in the same order and with the same values, apart from the
    contrast. Sending them again restores a controller whose settings
    were changed by a corrupted transfer.
    """
    external_vcc = getattr(driver, "external_vcc", False)
    page_addressing = getattr(driver, "page_addressing", False)
    commands = [
        0x20,  # memory addressing mode
        0x10 if page_addressing else 0x00,
        0x40,  # display start line 0
        0xA0 | 0x01,  # column 127 mapped to SEG0
        0xA8,  # multiplex ratio
        driver.height - 1,
        0xC0 | 0x08,  # scan from COM[N] to COM0
        0xD3,  # display offset
        0x00,
        0xDA,  # COM pins
        0x02 if driver.width > 2 * driver.height else 0x12,
        0xD5,  # clock divide ratio and oscillator frequency
        0x80,
        0xD9,  # pre-charge period
        0x22 if external_vcc else 0xF1,
        0xDB,  # VCOMH deselect level
        0x30,
        0x81,  # contrast
        contrast,
        0xA4,  # output follows RAM
        0xA6,  # not inverted
        0xAD,  # internal IREF
        0x30,
        0x8D,  # charge pump
        0x10 if external_vcc else 0x14,
    ]
    if display_on:
        commands.append(0xAF)
    return commands


class Display:
    """
    An OLED display that shows :class:`~adafruitdisplay.frames.Frame`s.

    The whole screen goes to the controller in one I2C transfer, led by
    a byte that marks the rest as pixels. If noise corrupts that byte,
    the pixels are read as commands instead, and a black screen is
    mostly ``0x00``, so a stray ``0x81`` (set contrast) leaves the
    display dim until the controller is set up again. To recover
    without a reboot, the display sends its settings again every
    ``refresh_seconds`` and after any failed transfer.

    Use it as a context manager to blank the screen when you're done::

        with Display.open() as display:
            display.show(frame)
    """

    def __init__(
        self,
        driver: Driver,
        *,
        rotate: int = 0,
        contrast: int = DEFAULT_CONTRAST,
        refresh_seconds: float = REFRESH_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rotate not in (0, 180):
            raise ValueError(f"rotate must be 0 or 180, not {rotate}")
        if not 0 <= contrast <= 255:
            raise ValueError(f"contrast runs from 0 to 255, not {contrast}")
        self.driver = driver
        self.width = driver.width
        self.height = driver.height
        self.rotate = rotate
        self.contrast = contrast
        self.refresh_seconds = refresh_seconds
        self.clock = clock
        self._last: bytes | None = None
        self._next_refresh = float("-inf")
        self.clear()

    @classmethod
    def open(
        cls,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        address: int = DEFAULT_ADDRESS,
        **options: object,
    ) -> Display:
        """
        Open the SSD1306 on I2C. See :func:`open_ssd1306`.

        Keyword options are passed on to :class:`Display`.
        """
        return cls(open_ssd1306(width, height, address), **options)  # type: ignore[arg-type]

    def refresh(self) -> None:
        """
        Send the controller's settings again, keeping the display on.
        """
        for command in settings_commands(self.driver, self.contrast):
            self.driver.write_cmd(command)
        self._next_refresh = self.clock() + self.refresh_seconds

    def clear(self) -> None:
        """
        Blank the screen.
        """
        self._send(Image.new("1", (self.width, self.height)))

    def show(self, frame: Frame) -> None:
        """
        Put a frame on the screen, unless it's already there.
        """
        image = frame.image
        if self.rotate == 180:
            image = image.transpose(Image.Transpose.ROTATE_180)
        if self.clock() < self._next_refresh and image.tobytes() == self._last:
            return
        self._send(image)

    def _send(self, image: Image.Image) -> None:
        refreshed = False
        if self.clock() >= self._next_refresh:
            self.refresh()
            refreshed = True
        try:
            self._write(image)
        except OSError as error:
            if refreshed:
                raise
            log.warning("display write failed, setting it up again: %s", error)
            self.refresh()
            self._write(image)

    def _write(self, image: Image.Image) -> None:
        self.driver.image(image)
        self.driver.show()
        self._last = image.tobytes()

    def __enter__(self) -> Display:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.clear()
