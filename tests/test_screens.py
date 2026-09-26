"""
Tests for the screens, the carousel and the HTTP switch.
"""

import json
import random
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

from adafruitdisplay import (
    Carousel,
    ControlServer,
    Display,
    IdentityScreen,
    PreviewDriver,
    ScreenSaver,
    Settings,
    SystemScreen,
    SystemStats,
    TextFrame,
    available_screens,
    format_uptime,
)
from adafruitdisplay.cli import main

GIB = 1024**3
STATS = SystemStats(
    hostname="pi-hole1",
    ip_address="192.168.100.200",
    load_averages=(0.10, 0.52, 0.30),
    temperature=48.3,
    memory_used=300 * 1024**2,
    memory_total=1000 * 1024**2,
    disk_used=3 * GIB,
    disk_total=16 * GIB,
    uptime=3 * 86400 + 4 * 3600 + 5 * 60,
)


def read_stats() -> SystemStats:
    return STATS


@pytest.fixture
def display(tmp_path: Path) -> Display:
    return Display(PreviewDriver(tmp_path / "frame.png"))


class Clock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Named:
    def __init__(self, display: Display, name: str) -> None:
        self.frame = TextFrame(display)
        self.name = name
        self.closed = False

    def render(self) -> TextFrame:
        self.frame.clear()
        self.frame.add_line(self.name)
        return self.frame

    def close(self) -> None:
        self.closed = True


def showing(display: Display) -> bytes:
    driver = display.driver
    assert isinstance(driver, PreviewDriver)
    return driver.frame.tobytes()


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(59, "0m"), (3 * 3600 + 7 * 60, "3h, 7m"), (2 * 86400 + 60, "2d, 0h, 1m")],
)
def test_format_uptime(seconds: float, text: str) -> None:
    assert format_uptime(seconds) == text


def test_identity_screen(display: Display) -> None:
    frame = IdentityScreen(display, Settings(), read_stats).render()

    assert frame.lines == ["pi-hole1", "192.168.100.200"]


def test_system_screen(display: Display) -> None:
    frame = SystemScreen(display, Settings(), read_stats).render()

    assert frame.lines == ["CPU: 0.52 (48°C)", "Mem: 30.0%", "Dsk: 19%", "Up: 3d, 4h, 5m"]


def test_system_screen_in_fahrenheit(display: Display) -> None:
    frame = SystemScreen(display, Settings(fahrenheit=True), read_stats).render()

    assert frame.lines[0] == "CPU: 0.52 (119°F)"


def test_screensaver_moves_but_stays_on_screen(display: Display) -> None:
    saver = ScreenSaver(display, Settings(), read_stats, rng=random.Random(4))
    positions = set()
    for _ in range(20):
        image = saver.render().image
        bbox = image.getbbox()
        assert bbox is not None
        assert bbox[2] <= display.width
        assert bbox[3] <= display.height
        positions.add(bbox[:2])

    assert len(positions) > 5


def test_builtin_screens_are_registered() -> None:
    screens = available_screens()

    assert screens["identity"] is IdentityScreen
    assert screens["system"] is SystemScreen


def test_carousel_changes_screens_on_the_beat(display: Display) -> None:
    clock = Clock(now=12.0)
    screens = [Named(display, "A"), Named(display, "B"), Named(display, "C")]
    carousel = Carousel(
        display, screens, Named(display, "saver"), on=True, clock=clock, sleep=clock.sleep
    )

    shown = []
    for _ in range(4):
        carousel.step()
        shown.append(showing(display))

    assert clock.sleeps == [3.0, 5.0, 5.0, 5.0]
    order = (screens[0], screens[1], screens[2], screens[0])
    expected = [screen.render().image.tobytes() for screen in order]
    assert shown == expected


def test_carousel_shows_the_screensaver_when_off(display: Display) -> None:
    clock = Clock(now=1.0)
    saver = Named(display, "saver")
    carousel = Carousel(display, [Named(display, "A")], saver, clock=clock, sleep=clock.sleep)

    carousel.step()

    assert clock.sleeps == [2.0]
    assert showing(display) == saver.render().image.tobytes()


def test_a_failing_screen_shows_its_error(display: Display) -> None:
    class Broken:
        def render(self) -> TextFrame:
            raise RuntimeError("no data")

    clock = Clock()
    carousel = Carousel(
        display, [Broken()], Named(display, "saver"), on=True, clock=clock, sleep=clock.sleep
    )

    carousel.step()

    assert carousel._error_frame.lines == ["Broken", "no data"]


def test_carousel_closes_its_screens(display: Display) -> None:
    screens = [Named(display, "A")]
    saver = Named(display, "saver")

    Carousel(display, screens, saver).close()

    assert screens[0].closed
    assert saver.closed


def test_control_server_switches_the_carousel(display: Display) -> None:
    carousel = Carousel(display, [Named(display, "A")], Named(display, "saver"))
    server = ControlServer(carousel, "127.0.0.1", 0)
    server.start()
    host, port = server.address
    base = f"http://{host}:{port}"

    def get(path: str) -> dict:
        with urllib.request.urlopen(base + path, timeout=5) as response:
            assert response.headers["Content-Type"] == "application/json"
            return json.load(response)

    try:
        assert get("/") == {"status": "off"}
        assert get("/on") == {"status": "on"}
        assert carousel.on
        assert get("/") == {"status": "on"}
        assert get("/off") == {"status": "off"}
        assert not carousel.on
        with pytest.raises(urllib.error.HTTPError):
            get("/reboot")
    finally:
        server.stop()


def test_cli_preview_writes_every_screen(tmp_path: Path) -> None:
    assert main(["--preview", str(tmp_path), "--fahrenheit"]) == 0

    for name in ("identity", "system", "screensaver"):
        image = Image.open(tmp_path / f"{name}.png")
        assert image.size == (128, 32)
        assert image.getbbox() is not None
