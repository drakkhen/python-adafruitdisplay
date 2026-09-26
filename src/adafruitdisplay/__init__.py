"""
Draw text and status screens on a small SSD1306 OLED, like the PiOLED.

    from adafruitdisplay import Display, TextFrame

    with Display.open() as display:
        frame = TextFrame(display)
        frame.add_line("Hello")
        display.show(frame)
"""

from importlib.metadata import PackageNotFoundError, version

from .display import Display, Driver, PreviewDriver, open_ssd1306
from .frames import (
    OFF,
    ON,
    SILKSCREEN,
    SILKSCREEN_BOLD,
    Frame,
    SystemStatusFrame,
    TextFrame,
    address_line,
    load_font,
)
from .stats import SystemStats, read_system_stats

try:
    __version__ = version("adafruitdisplay")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "OFF",
    "ON",
    "SILKSCREEN",
    "SILKSCREEN_BOLD",
    "Display",
    "Driver",
    "Frame",
    "PreviewDriver",
    "SystemStats",
    "SystemStatusFrame",
    "TextFrame",
    "address_line",
    "load_font",
    "open_ssd1306",
    "read_system_stats",
]
