"""
Screens: things that know how to draw themselves into a frame.

Packages add screens through the ``adafruitdisplay.screens`` entry point
group. Each entry point names a factory that takes the display and the
shared :class:`Settings` and returns a :class:`Screen`.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol

from .display import Display
from .frames import SILKSCREEN, Frame, TextFrame
from .stats import SystemStats, read_system_stats

ENTRY_POINT_GROUP = "adafruitdisplay.screens"


@dataclass(frozen=True, slots=True)
class Settings:
    """
    Options shared by every screen: fonts and temperature units.

    Fonts are bundled font names or paths to TrueType files.
    """

    title_font: str = SILKSCREEN
    title_size: int = 16
    text_font: str = SILKSCREEN
    text_size: int = 8
    fahrenheit: bool = False


class Screen(Protocol):
    """
    Something the carousel can put on the display.
    """

    def render(self) -> Frame:
        """
        Draw the current contents and return the frame.
        """
        ...


ScreenFactory = Callable[[Display, Settings], Screen]


def available_screens() -> dict[str, ScreenFactory]:
    """
    Return every installed screen factory by name.
    """
    return {point.name: point.load() for point in entry_points(group=ENTRY_POINT_GROUP)}


class IdentityScreen:
    """
    The hostname and IP address in large type.
    """

    def __init__(
        self,
        display: Display,
        settings: Settings,
        read_stats: Callable[[], SystemStats] = read_system_stats,
    ) -> None:
        self.frame = TextFrame(display, settings.title_size, settings.title_font)
        self.min_size = settings.text_size
        self.read_stats = read_stats

    def render(self) -> TextFrame:
        """
        Draw the hostname over the address.
        """
        stats = self.read_stats()
        self.frame.clear()
        self.frame.center_lines(
            [stats.hostname, stats.ip_address or "no network"], min_size=self.min_size
        )
        return self.frame


class SystemScreen:
    """
    Load and temperature, memory and disk, and uptime, in small type.
    """

    def __init__(
        self,
        display: Display,
        settings: Settings,
        read_stats: Callable[[], SystemStats] = read_system_stats,
    ) -> None:
        self.frame = TextFrame(display, settings.text_size, settings.text_font)
        # Small pixel fonts need a pixel between lines.
        self.line_height = settings.text_size + 2
        self.fahrenheit = settings.fahrenheit
        self.read_stats = read_stats

    def render(self) -> TextFrame:
        """
        Draw three labelled lines, with disk use on the right.
        """
        stats = self.read_stats()
        frame = self.frame
        frame.clear()

        labels = ("CPU:", "Mem:", "Up:")
        value_x = max(frame.draw.textlength(label, font=frame.font) for label in labels) + 5
        values = (
            f"{stats.load_averages[1]:.2f}{self._temperature(stats)}",
            f"{stats.memory_percent:.1f}%",
            format_uptime(stats.uptime),
        )
        for row, (label, value) in enumerate(zip(labels, values, strict=True)):
            y = row * self.line_height
            frame.draw.text((0, y), label, font=frame.font, fill=1)
            frame.draw.text((value_x, y), value, font=frame.font, fill=1)

        disk = f"Dsk: {stats.disk_percent:.0f}%"
        disk_x = frame.width - frame.draw.textlength(disk, font=frame.font)
        frame.draw.text((disk_x, self.line_height), disk, font=frame.font, fill=1)
        frame.lines = [f"{label} {value}" for label, value in zip(labels, values, strict=True)]
        frame.lines.insert(2, disk)
        return frame

    def _temperature(self, stats: SystemStats) -> str:
        if stats.temperature is None:
            return ""
        if self.fahrenheit:
            return f" ({stats.temperature * 1.8 + 32:.0f}°F)"
        return f" ({stats.temperature:.0f}°C)"


class ScreenSaver:
    """
    The hostname in small type at a random spot, so no pixel stays lit.
    """

    def __init__(
        self,
        display: Display,
        settings: Settings,
        read_stats: Callable[[], SystemStats] = read_system_stats,
        rng: random.Random | None = None,
    ) -> None:
        self.frame = TextFrame(display, settings.text_size, settings.text_font)
        self.read_stats = read_stats
        self.rng = rng or random.Random()

    def render(self) -> TextFrame:
        """
        Draw the hostname somewhere new.
        """
        frame = self.frame
        text = frame.fit(self.read_stats().hostname)
        left, top, right, bottom = frame.draw.textbbox((0, 0), text, font=frame.font)
        x = self.rng.randint(0, max(0, frame.width - int(right - left))) - left
        y = self.rng.randint(0, max(0, frame.height - int(bottom - top))) - top
        frame.clear()
        frame.draw.text((x, y), text, font=frame.font, fill=1)
        frame.lines = [text]
        return frame


def format_uptime(seconds: float) -> str:
    """
    Format an uptime as ``3d, 4h, 5m``, leaving out leading zeros.
    """
    minutes = int(seconds // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d, {hours}h, {minutes}m"
    if hours:
        return f"{hours}h, {minutes}m"
    return f"{minutes}m"
