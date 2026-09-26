"""
The ``adafruitdisplay-stats`` command: system status on the OLED.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from collections.abc import Sequence
from types import FrameType

from . import __version__
from .display import Display, PreviewDriver
from .frames import SystemStatusFrame


def main(argv: Sequence[str] | None = None) -> int:
    """
    Show system status until interrupted, or render one frame to a PNG.
    """
    parser = argparse.ArgumentParser(
        prog="adafruitdisplay-stats",
        description="Show the host's address, load, memory and disk on an SSD1306 OLED.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="seconds between updates (%(default)s)"
    )
    parser.add_argument(
        "--preview", metavar="PNG", help="render one frame to this file instead of the screen"
    )
    args = parser.parse_args(argv)

    if args.preview:
        display = Display(PreviewDriver(args.preview))
        frame = SystemStatusFrame(display)
        frame.update()
        display.show(frame)
        return 0

    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    try:
        with Display.open() as display:
            frame = SystemStatusFrame(display)
            while True:
                frame.update()
                display.show(frame)
                time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def _raise_keyboard_interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
