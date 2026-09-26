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
    TextFrame,
    load_font,
    open_ssd1306,
    settings_commands,
)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def driver(tmp_path: Path) -> PreviewDriver:
    return PreviewDriver(tmp_path / "frame.png")


@pytest.fixture
def display(driver: PreviewDriver) -> Display:
    return Display(driver)


def lit_rows(image: Image.Image) -> list[int]:
    width, height = image.size
    return [y for y in range(height) if any(image.getpixel((x, y)) for x in range(width))]


def lit_columns(image: Image.Image) -> list[int]:
    width, height = image.size
    return [x for x in range(width) if any(image.getpixel((x, y)) for y in range(height))]


def test_display_blanks_the_screen_on_open_and_exit(driver: PreviewDriver) -> None:
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
    assert abs(columns[0] - (display.width - 1 - columns[-1])) <= 1
    assert abs(rows[0] - (display.height - 1 - rows[-1])) <= 1


def test_center_lines_keeps_tall_glyphs_on_screen(display: Display) -> None:
    frame = TextFrame(display, font_size=16)
    frame.center_lines(["HOST", "10.0.0.2"])

    rows = lit_rows(frame.image)
    assert rows[0] > 0
    assert rows[-1] < display.height - 1
    assert frame.lines == ["HOST", "10.0.0.2"]


def test_inverted_frame(display: Display) -> None:
    frame = TextFrame(display, font_size=32)
    frame.clear(ON)
    frame.center_text("7", fill=0)

    assert frame.image.getpixel((0, 0))
    assert frame.image.convert("L").getextrema() == (0, 255)


def test_long_lines_are_trimmed_to_fit(display: Display) -> None:
    frame = TextFrame(display)
    frame.add_line("x" * 60)

    assert frame.fits(frame.lines[0])
    assert not frame.fits(frame.lines[0] + "x")


def test_fonts_load_by_name_or_path() -> None:
    bundled = Path(__file__).parent.parent / "src" / "adafruitdisplay" / "fonts" / "slkscrb.ttf"

    assert load_font("slkscrb.ttf", 16).size == 16
    assert load_font(str(bundled), 8).size == 8


def test_rotate_180_turns_the_image_over(driver: PreviewDriver) -> None:
    display = Display(driver, rotate=180)
    frame = TextFrame(display)
    frame.draw.point((0, 0), fill=ON)

    display.show(frame)

    assert driver.frame.getpixel((display.width - 1, display.height - 1))
    assert not driver.frame.getpixel((0, 0))


def test_unchanged_frames_are_not_sent_again(driver: PreviewDriver) -> None:
    clock = Clock()
    display = Display(driver, clock=clock)
    frame = TextFrame(display)
    frame.add_line("same")

    display.show(frame)
    display.show(frame)
    shows = driver.shows
    frame.add_line("changed")
    display.show(frame)

    assert shows == 2
    assert driver.shows == 3


def test_settings_are_sent_again_on_a_schedule(driver: PreviewDriver) -> None:
    clock = Clock()
    display = Display(driver, clock=clock, refresh_seconds=300)
    frame = TextFrame(display)
    frame.add_line("static")
    display.show(frame)
    sent = len(driver.commands)

    clock.now = 299
    display.show(frame)
    assert len(driver.commands) == sent

    clock.now = 300
    display.show(frame)
    assert driver.commands[sent:] == settings_commands(driver)
    assert driver.shows == 3


def test_a_failed_write_resets_the_controller_and_retries(driver: PreviewDriver) -> None:
    clock = Clock()
    display = Display(driver, clock=clock)
    frame = TextFrame(display)
    frame.add_line("retry")
    failures = [OSError("[Errno 121] Remote I/O error")]
    original = driver.show

    def flaky_show() -> None:
        if failures:
            raise failures.pop()
        original()

    driver.show = flaky_show  # type: ignore[method-assign]
    clock.now = 10
    sent = len(driver.commands)

    display.show(frame)

    assert driver.commands[sent:] == settings_commands(driver)
    assert lit_rows(Image.open(driver.path))


def test_contrast_is_part_of_the_settings(driver: PreviewDriver) -> None:
    Display(driver, contrast=0x40)

    assert driver.commands[driver.commands.index(0x81) + 1] == 0x40


def test_invalid_options(driver: PreviewDriver) -> None:
    with pytest.raises(ValueError):
        Display(driver, rotate=90)
    with pytest.raises(ValueError):
        Display(driver, contrast=300)


def test_settings_match_the_real_driver() -> None:
    ssd1306 = pytest.importorskip("adafruit_ssd1306")

    class Recording(ssd1306._SSD1306):
        def __init__(self, width: int, height: int) -> None:
            self.commands: list[int] = []
            buffer = memoryview(bytearray(width * height // 8))
            super().__init__(
                buffer, width, height, external_vcc=False, reset=None, page_addressing=False
            )

        def write_cmd(self, cmd: int) -> None:
            self.commands.append(cmd)

        def write_framebuf(self) -> None:
            pass

    for width, height in ((128, 32), (128, 64)):
        real = Recording(width, height)
        # init_display turns the display off first, then sends the rest.
        after_off = real.commands.index(0xAE) + 1
        startup = real.commands[after_off:]
        startup = startup[: startup.index(0xAF) + 1]
        assert settings_commands(real) == startup, (width, height)


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


def test_center_lines_shrinks_the_font_to_fit(display: Display) -> None:
    frame = TextFrame(display, font_size=16)
    lines = ["Queries: 36,692", "Blocked: 9,013"]
    assert not all(frame.fits(line) for line in lines)

    frame.center_lines(lines, min_size=8)

    assert frame.lines == lines
    assert frame.font_size == 16


def test_center_lines_trims_what_still_does_not_fit(display: Display) -> None:
    frame = TextFrame(display, font_size=16)

    frame.center_lines(["x" * 80], min_size=8)

    assert frame.lines[0] == frame.fit("x" * 80, load_font(frame.font_name, 8))
