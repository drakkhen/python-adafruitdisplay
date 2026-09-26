"""
Frames: 1-bit images sized to the display, and text drawing helpers.
"""

from __future__ import annotations

from importlib.resources import files
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from .stats import SystemStats, read_system_stats

if TYPE_CHECKING:
    from .display import Display

ON = 1
OFF = 0

SILKSCREEN = "slkscr.ttf"
SILKSCREEN_BOLD = "slkscrb.ttf"

# Silkscreen's glyphs sit two pixels below the top of their em box.
_TOP_PADDING = -2

MIB = 1024 * 1024
GIB = 1024 * MIB


def load_font(name: str = SILKSCREEN, size: int = 8) -> ImageFont.FreeTypeFont:
    """
    Load one of the bundled fonts at ``size`` pixels.

    Silkscreen is a pixel font, so multiples of 8 draw crisply.
    """
    data = files("adafruitdisplay").joinpath("fonts", name).read_bytes()
    return ImageFont.truetype(BytesIO(data), size)


class Frame:
    """
    A blank 1-bit image the size of a display.
    """

    def __init__(self, display: Display) -> None:
        self.width = display.width
        self.height = display.height
        self.image = Image.new("1", (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)

    def clear(self, fill: int = OFF) -> None:
        """
        Fill the whole frame with ``fill``.
        """
        self.draw.rectangle((0, 0, self.width, self.height), fill=fill)


class TextFrame(Frame):
    """
    A frame for lines of text, drawn top to bottom, or centred text.
    """

    def __init__(self, display: Display, font_size: int = 8, font: str = SILKSCREEN) -> None:
        super().__init__(display)
        self.top = _TOP_PADDING
        self.lines: list[str] = []
        self.set_font(font, font_size)

    def set_font(self, name: str, size: int) -> None:
        """
        Switch to a bundled font. Line spacing follows the size.
        """
        self.font = load_font(name, size)
        self.font_size = size

    def clear(self, fill: int = OFF) -> None:
        """
        Fill the frame and go back to the first line.
        """
        super().clear(fill)
        self.lines = []

    def fits(self, text: str) -> bool:
        """
        Whether ``text`` fits across the frame in the current font.
        """
        return self.draw.textlength(text, font=self.font) <= self.width

    def fit(self, text: str) -> str:
        """
        Trim ``text`` from the end until it fits across the frame.
        """
        while text and not self.fits(text):
            text = text[:-1]
        return text

    def first_fitting(self, *candidates: str) -> str:
        """
        Return the first candidate that fits, or the last one trimmed.
        """
        for text in candidates:
            if self.fits(text):
                return text
        return self.fit(candidates[-1])

    def add_line(self, text: str, fill: int = ON) -> None:
        """
        Draw ``text`` on the next line, trimmed to the frame's width.
        """
        text = self.fit(text)
        position = (0, self.top + len(self.lines) * self.font_size)
        self.draw.text(position, text, font=self.font, fill=fill)
        self.lines.append(text)

    def center_text(self, text: str, fill: int = ON) -> None:
        """
        Draw ``text`` in the middle of the frame.
        """
        left, top, right, bottom = self.draw.textbbox((0, 0), text, font=self.font)
        x = (self.width - (right - left)) / 2 - left
        y = (self.height - (bottom - top)) / 2 - top
        self.draw.text((x, y), text, font=self.font, fill=fill)


class SystemStatusFrame(TextFrame):
    """
    Four lines about the host: address, load, memory and disk.
    """

    def update(self, stats: SystemStats | None = None) -> None:
        """
        Redraw from ``stats``, or from a fresh reading of this machine.
        """
        if stats is None:
            stats = read_system_stats()
        temperature = "" if stats.temperature is None else f" ({stats.temperature:.1f}°C)"

        self.clear()
        self.add_line(address_line(self, stats))
        self.add_line(f"CPU Load: {stats.load_average:.2f}{temperature}")
        self.add_line(
            f"Mem: {stats.memory_used // MIB}/{stats.memory_total // MIB}MB "
            f"{stats.memory_percent:.0f}%"
        )
        self.add_line(
            f"Disk: {stats.disk_used / GIB:.0f}/{stats.disk_total / GIB:.0f}GB "
            f"{stats.disk_percent:.0f}%"
        )


def address_line(frame: TextFrame, stats: SystemStats) -> str:
    """
    Format the address and hostname line shared by status screens.

    Long addresses drop the ``IP:`` label, then the parentheses, before
    the hostname is trimmed.
    """
    address = stats.ip_address or "no network"
    return frame.first_fitting(
        f"IP: {address} ({stats.hostname})",
        f"{address} ({stats.hostname})",
        f"{address} {stats.hostname}",
    )
