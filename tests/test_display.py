"""
Tests for frames and the display, drawn through the preview driver.
"""

import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from adafruitdisplay import (
    ON,
    Display,
    PreviewDriver,
    SystemStats,
    SystemStatusFrame,
    TextFrame,
    load_font,
    open_ssd1306,
)
from adafruitdisplay.cli import main

GIB = 1024**3

BUSY_PI = SystemStats(
    hostname="pi-hole",
    ip_address="192.168.100.200",
    load_average=12.34,
    temperature=85.5,
    memory_used=3900 * 1024**2,
    memory_total=7999 * 1024**2,
    disk_used=120 * GIB,
    disk_total=256 * GIB,
)


@pytest.fixture
def display(tmp_path: Path) -> Display:
    return Display(PreviewDriver(tmp_path / "frame.png"))


def lit_rows(image: Image.Image) -> list[int]:
    width, height = image.size
    return [y for y in range(height) if any(image.getpixel((x, y)) for x in range(width))]


def lit_columns(image: Image.Image) -> list[int]:
    width, height = image.size
    return [x for x in range(width) if any(image.getpixel((x, y)) for y in range(height))]


def test_display_blanks_the_screen_on_open_and_exit(tmp_path: Path) -> None:
    driver = PreviewDriver(tmp_path / "frame.png")
    with Display(driver) as display:
        frame = TextFrame(display)
        frame.add_line("Hello")
        display.show(frame)
        assert lit_rows(Image.open(driver.path))

    assert lit_rows(Image.open(driver.path)) == []


def test_lines_stack_down_the_frame(display: Display) -> None:
    frame = TextFrame(display)
    frame.add_line("TOP")
    first = lit_rows(frame.image)
    frame.add_line("NEXT")
    both = lit_rows(frame.image)

    assert max(first) < 8
    assert max(both) >= 8
    assert min(set(both) - set(first)) >= 8


def test_center_text_is_centred(display: Display) -> None:
    frame = TextFrame(display, font_size=32)
    frame.center_text("123")

    columns, rows = lit_columns(frame.image), lit_rows(frame.image)
    left_margin, right_margin = columns[0], display.width - 1 - columns[-1]
    top_margin, bottom_margin = rows[0], display.height - 1 - rows[-1]
    assert abs(left_margin - right_margin) <= 1
    assert abs(top_margin - bottom_margin) <= 1


def test_inverted_frame(display: Display) -> None:
    frame = TextFrame(display, font_size=32)
    frame.clear(ON)
    frame.center_text("7", fill=0)

    assert frame.image.getpixel((0, 0))
    assert frame.image.convert("L").getextrema() == (0, 255)


def test_status_lines_fit_the_display(display: Display) -> None:
    frame = SystemStatusFrame(display)
    frame.update(BUSY_PI)

    assert frame.lines == [
        "192.168.100.200 (pi-hole)",
        "CPU Load: 12.34 (85.5°C)",
        "Mem: 3900/7999MB 49%",
        "Disk: 120/256GB 47%",
    ]
    assert all(frame.fits(line) for line in frame.lines)
    assert max(lit_rows(frame.image)) < display.height


def test_short_addresses_keep_the_label(display: Display) -> None:
    frame = SystemStatusFrame(display)
    frame.update(SystemStats("pi", "10.0.0.2", 0.1, None, 1, 2, 1, 2))

    assert frame.lines[0] == "IP: 10.0.0.2 (pi)"


def test_long_lines_are_trimmed_to_fit(display: Display) -> None:
    frame = TextFrame(display)
    frame.add_line("x" * 60)

    assert frame.fits(frame.lines[0])
    assert frame.lines[0] == frame.fit("x" * 60)
    assert not frame.fits(frame.lines[0] + "x")


def test_status_without_temperature_or_network(display: Display) -> None:
    frame = SystemStatusFrame(display)
    stats = SystemStats("box", None, 0.5, None, 1, 2, 1, 2)

    frame.update(stats)

    assert lit_rows(frame.image)


def test_bold_font_loads_from_the_package() -> None:
    assert load_font("slkscrb.ttf", 16).size == 16


def test_preview_driver_rejects_the_wrong_size(tmp_path: Path) -> None:
    driver = PreviewDriver(tmp_path / "frame.png")

    with pytest.raises(ValueError):
        driver.image(Image.new("1", (64, 32)))


def test_open_ssd1306_uses_the_default_i2c_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class FakeSSD1306:
        def __init__(self, width: int, height: int, i2c: object, addr: int) -> None:
            calls.append((width, height, i2c, addr))

    bus = object()
    monkeypatch.setitem(sys.modules, "board", types.SimpleNamespace(I2C=lambda: bus))
    monkeypatch.setitem(
        sys.modules, "adafruit_ssd1306", types.SimpleNamespace(SSD1306_I2C=FakeSSD1306)
    )

    open_ssd1306()

    assert calls == [(128, 32, bus, 0x3C)]


def test_cli_preview_writes_a_png(tmp_path: Path) -> None:
    target = tmp_path / "stats.png"

    assert main(["--preview", str(target)]) == 0

    image = Image.open(target)
    assert image.size == (128, 32)
    assert lit_rows(image)
