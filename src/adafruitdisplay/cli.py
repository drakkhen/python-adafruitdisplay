"""
The ``oled-display`` command: a carousel of screens on the OLED.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from . import __version__
from .carousel import Carousel, ControlServer
from .display import DEFAULT_CONTRAST, Display, PreviewDriver
from .screens import ScreenSaver, Settings, available_screens

DEFAULT_SCREENS = ("identity", "system")
DEFAULTS = Settings()


def main(
    argv: Sequence[str] | None = None,
    *,
    prog: str = "oled-display",
    default_screens: Sequence[str] = DEFAULT_SCREENS,
) -> int:
    """
    Run the carousel until interrupted, and return the exit status.

    Other packages pass their own ``prog`` and default screens.
    """
    factories = available_screens()
    args = _parser(prog, sorted(factories), default_screens).parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    settings = Settings(
        title_font=args.title_font,
        title_size=args.title_size,
        text_font=args.text_font,
        text_size=args.text_size,
        fahrenheit=args.fahrenheit,
    )
    names = args.screen or list(default_screens)

    if args.preview:
        return _preview(Path(args.preview), names, factories, settings)

    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    try:
        with Display.open(rotate=args.rotate, contrast=args.contrast) as display:
            carousel = Carousel(
                display,
                [factories[name](display, settings) for name in names],
                ScreenSaver(display, settings),
                on=args.on,
            )
            server = _start_control(carousel, args.control)
            try:
                carousel.run()
            finally:
                if server is not None:
                    server.stop()
                carousel.close()
    except KeyboardInterrupt:
        pass
    return 0


def _parser(
    prog: str, screen_names: list[str], default_screens: Sequence[str]
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog, description="Show a carousel of screens on an SSD1306 OLED."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--screen",
        action="append",
        choices=screen_names,
        help=f"a screen to show; repeat for more (default: {', '.join(default_screens)})",
    )
    parser.add_argument(
        "--on", action="store_true", help="start showing screens instead of the screen saver"
    )
    parser.add_argument(
        "--control",
        metavar="HOST:PORT",
        help="serve /on, /off and / for switching the screens (e.g. 0.0.0.0:5001)",
    )
    parser.add_argument(
        "--rotate", type=int, choices=(0, 180), default=0, help="for upside-down mounting"
    )
    parser.add_argument(
        "--contrast",
        type=int,
        default=DEFAULT_CONTRAST,
        help="brightness, 0-255 (%(default)s); lower slows OLED wear",
    )
    parser.add_argument("--title-font", default=DEFAULTS.title_font, help="font name or path")
    parser.add_argument("--title-size", type=int, default=DEFAULTS.title_size)
    parser.add_argument("--text-font", default=DEFAULTS.text_font, help="font name or path")
    parser.add_argument("--text-size", type=int, default=DEFAULTS.text_size)
    parser.add_argument("--fahrenheit", action="store_true", help="show °F instead of °C")
    parser.add_argument(
        "--preview", metavar="DIR", help="save each screen as a PNG in DIR and exit"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log more detail")
    return parser


def _start_control(carousel: Carousel, address: str | None) -> ControlServer | None:
    if address is None:
        return None
    host, _, port = address.rpartition(":")
    server = ControlServer(carousel, host or "127.0.0.1", int(port))
    server.start()
    logging.getLogger(__name__).info("control server on %s:%s", *server.address)
    return server


def _preview(directory: Path, names: list[str], factories: dict, settings: Settings) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    display = Display(PreviewDriver(directory / "blank.png"))
    screens = {name: factories[name](display, settings) for name in names}
    screens["screensaver"] = ScreenSaver(display, settings)
    for name, screen in screens.items():
        screen.render().image.save(directory / f"{name}.png")
        close = getattr(screen, "close", None)
        if close is not None:
            close()
    return 0


def _raise_keyboard_interrupt(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
