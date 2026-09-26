"""
The carousel: screens in turn when on, a screen saver when off.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .display import Display
from .frames import Frame, TextFrame
from .screens import Screen

log = logging.getLogger(__name__)

SCREEN_SECONDS = 5.0
SAVER_SECONDS = 3.0


class Carousel:
    """
    Show each screen for ``screen_seconds``, or the saver when off.

    Screen changes line up with the wall clock, so several displays
    running the carousel change screens together. :attr:`on` can be
    flipped from another thread, such as the :class:`ControlServer`.
    """

    def __init__(
        self,
        display: Display,
        screens: Sequence[Screen],
        screensaver: Screen,
        *,
        on: bool = False,
        screen_seconds: float = SCREEN_SECONDS,
        saver_seconds: float = SAVER_SECONDS,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not screens:
            raise ValueError("the carousel needs at least one screen")
        self.display = display
        self.screens = list(screens)
        self.screensaver = screensaver
        self.screen_seconds = screen_seconds
        self.saver_seconds = saver_seconds
        self.clock = clock
        self.sleep = sleep
        self._on = threading.Event()
        if on:
            self._on.set()
        self._error_frame = TextFrame(display)

    @property
    def on(self) -> bool:
        """
        Whether screens are showing; ``False`` means the screen saver.
        """
        return self._on.is_set()

    @on.setter
    def on(self, value: bool) -> None:
        if value:
            self._on.set()
        else:
            self._on.clear()

    def run(self) -> None:
        """
        Show screens until interrupted.
        """
        while True:
            self.step()

    def step(self) -> None:
        """
        Draw the next screen, wait for its turn, and show it.
        """
        now = self.clock()
        if self.on:
            period = self.screen_seconds
            slot = int(now // period) + 1
            screen = self.screens[slot % len(self.screens)]
        else:
            period = self.saver_seconds
            slot = int(now // period) + 1
            screen = self.screensaver
        # Draw ahead of time so a slow screen still changes on the beat.
        frame = self._render(screen)
        self.sleep(max(0.0, slot * period - self.clock()))
        self.display.show(frame)

    def close(self) -> None:
        """
        Close any screen that holds resources, such as a login session.
        """
        for screen in [*self.screens, self.screensaver]:
            close = getattr(screen, "close", None)
            if close is not None:
                close()

    def _render(self, screen: Screen) -> Frame:
        try:
            return screen.render()
        except Exception as error:
            log.exception("%s failed to draw", type(screen).__name__)
            frame = self._error_frame
            frame.clear()
            frame.add_line(type(screen).__name__)
            frame.add_line(str(error))
            return frame


class ControlServer:
    """
    Switch the carousel on and off over HTTP.

    ``GET /`` reports ``{"status": "on"}`` or ``{"status": "off"}``,
    and ``GET /on`` and ``GET /off`` switch it, as the
    homebridge-simple-http plugin expects.
    """

    def __init__(self, carousel: Carousel, host: str = "127.0.0.1", port: int = 5001) -> None:
        self.carousel = carousel

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                log.debug("%s " + format, self.address_string(), *args)

            def do_GET(self) -> None:
                if self.path in ("/on", "/off"):
                    carousel.on = self.path == "/on"
                    log.info("display switched %s", self.path[1:])
                elif self.path != "/":
                    self.send_error(404)
                    return
                body = json.dumps({"status": "on" if carousel.on else "off"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer((host, port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def address(self) -> tuple[str, int]:
        """
        The host and port the server listens on.
        """
        host, port = self.server.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        """
        Serve requests on a background thread.
        """
        self.thread.start()

    def stop(self) -> None:
        """
        Stop serving and release the port.
        """
        self.server.shutdown()
        self.server.server_close()
