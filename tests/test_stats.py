"""
Tests for the host readings.
"""

import socket
import types

import pytest

from adafruitdisplay import SystemStats, read_system_stats, stats


def test_reads_this_machine() -> None:
    reading = read_system_stats()

    assert reading.hostname
    assert "." not in reading.hostname
    assert 0 < reading.memory_used <= reading.memory_total
    assert 0 < reading.disk_used <= reading.disk_total
    assert reading.load_average >= 0


def test_percentages() -> None:
    reading = SystemStats("h", None, 0.0, None, 1, 4, 3, 4)

    assert reading.memory_percent == 25
    assert reading.disk_percent == 75


def test_temperature_prefers_the_soc_sensor(monkeypatch: pytest.MonkeyPatch) -> None:
    sensor = types.SimpleNamespace
    monkeypatch.setattr(
        stats.psutil,
        "sensors_temperatures",
        lambda: {"nvme": [sensor(current=40.0)], "cpu_thermal": [sensor(current=51.5)]},
        raising=False,
    )

    assert stats.cpu_temperature() == 51.5


def test_temperature_is_none_without_a_sensor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stats.psutil, "sensors_temperatures", lambda: {}, raising=False)

    assert stats.cpu_temperature() is None


def test_ip_address_is_none_without_a_route(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoRoute(socket.socket):
        def connect(self, address: object) -> None:
            raise OSError("Network is unreachable")

    monkeypatch.setattr(stats.socket, "socket", NoRoute)

    assert stats.primary_ip_address() is None
