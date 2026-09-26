"""
Draw text and status screens on a small SSD1306 OLED, like the PiOLED.

    from adafruitdisplay import Display, TextFrame

    with Display.open(rotate=180) as display:
        frame = TextFrame(display)
        frame.add_line("Hello")
        display.show(frame)

The ``oled-display`` command runs a carousel of screens with an
optional HTTP on/off switch.
"""

from importlib.metadata import PackageNotFoundError, version

from .carousel import Carousel, ControlServer
from .display import Display, Driver, PreviewDriver, open_ssd1306, settings_commands
from .frames import (
    OFF,
    ON,
    SILKSCREEN,
    SILKSCREEN_BOLD,
    Frame,
    TextFrame,
    address_line,
    load_font,
)
from .screens import (
    IdentityScreen,
    Screen,
    ScreenFactory,
    ScreenSaver,
    Settings,
    SystemScreen,
    available_screens,
    format_uptime,
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
    "Carousel",
    "ControlServer",
    "Display",
    "Driver",
    "Frame",
    "IdentityScreen",
    "PreviewDriver",
    "Screen",
    "ScreenFactory",
    "ScreenSaver",
    "Settings",
    "SystemScreen",
    "SystemStats",
    "TextFrame",
    "address_line",
    "available_screens",
    "format_uptime",
    "load_font",
    "open_ssd1306",
    "read_system_stats",
    "settings_commands",
]
