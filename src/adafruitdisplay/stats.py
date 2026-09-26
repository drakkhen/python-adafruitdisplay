"""
Readings about the machine the display is attached to.
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import socket
import time
from dataclasses import dataclass

import psutil

# Sensor names that report the SoC temperature, most specific first.
_TEMPERATURE_SENSORS = ("cpu_thermal", "soc_thermal", "coretemp", "k10temp")


@dataclass(frozen=True, slots=True)
class SystemStats:
    """
    A snapshot of the host's address, load, memory and disk use.
    """

    hostname: str
    ip_address: str | None
    # 1, 5 and 15 minute load averages.
    load_averages: tuple[float, float, float]
    temperature: float | None
    memory_used: int
    memory_total: int
    disk_used: int
    disk_total: int
    uptime: float

    @property
    def memory_percent(self) -> float:
        """
        Memory in use, as a percentage.
        """
        return 100 * self.memory_used / self.memory_total

    @property
    def load_average(self) -> float:
        """
        The one-minute load average.
        """
        return self.load_averages[0]

    @property
    def disk_percent(self) -> float:
        """
        Disk space in use on the root filesystem, as a percentage.
        """
        return 100 * self.disk_used / self.disk_total


def read_system_stats() -> SystemStats:
    """
    Take a :class:`SystemStats` snapshot of this machine.
    """
    memory = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    return SystemStats(
        hostname=socket.gethostname().split(".")[0],
        ip_address=primary_ip_address(),
        load_averages=os.getloadavg(),
        temperature=cpu_temperature(),
        memory_used=memory.total - memory.available,
        memory_total=memory.total,
        disk_used=disk.used,
        disk_total=disk.total,
        uptime=time.time() - psutil.boot_time(),
    )


def primary_ip_address() -> str | None:
    """
    Return the address this machine uses to reach other networks.

    No packets are sent: connecting a UDP socket only picks a route. On
    a network with no default route, fall back to the first IPv4
    address on an interface that's up. Returns ``None`` if there's
    neither.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            # TEST-NET-1 (RFC 5737), so nothing real is contacted.
            probe.connect(("192.0.2.1", 9))
        except OSError:
            return _interface_ip_address()
        return probe.getsockname()[0]


def _interface_ip_address() -> str | None:
    interfaces = psutil.net_if_stats()
    for name, addresses in psutil.net_if_addrs().items():
        if name not in interfaces or not interfaces[name].isup:
            continue
        for address in addresses:
            if address.family != socket.AF_INET:
                continue
            ip = ipaddress.IPv4Address(address.address)
            if not (ip.is_loopback or ip.is_link_local):
                return address.address
    return None


def cpu_temperature() -> float | None:
    """
    Return the CPU temperature in degrees Celsius, if a sensor has one.
    """
    reader = getattr(psutil, "sensors_temperatures", None)
    if reader is None:
        return None
    sensors = reader()
    for name in _TEMPERATURE_SENSORS:
        if sensors.get(name):
            return sensors[name][0].current
    return None
