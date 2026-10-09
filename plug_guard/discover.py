"""Locate the plug by MAC address — no DHCP reservation needed.

Works from WSL (reads the Windows ARP table via arp.exe after a ping sweep,
since WSL2 NAT forwards LAN traffic and thus populates the host ARP cache)
and from native Linux (ip neigh).
"""

from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_ARP_EXE = Path("/mnt/c/Windows/System32/ARP.EXE")

_IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")


def _norm_mac(mac: str) -> str:
    """Normalize any MAC format (dashes, uppercase) to colon-lowercase."""
    return mac.strip().lower().replace("-", ":")


def find_ip_by_mac(mac: str, arp_text: str) -> str | None:
    """Search an `arp -a` or `ip neigh` dump for the IP owning `mac`.

    Both formats put the IPv4 and the MAC (dash- or colon-separated) on the
    same line, so one regex pass suffices.
    """
    needle = _norm_mac(mac)
    for line in arp_text.splitlines():
        if needle in line.lower().replace("-", ":"):
            m = _IP_RE.search(line)
            if m:
                return m.group(1)
    return None


def arp_table() -> str:
    if _ARP_EXE.exists():  # running under WSL
        out = subprocess.run([str(_ARP_EXE), "-a"], capture_output=True, text=True)
        return out.stdout
    out = subprocess.run(["ip", "neigh"], capture_output=True, text=True)
    return out.stdout


def _ping(ip: str) -> bool:
    try:
        return subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip], capture_output=True
        ).returncode == 0
    except OSError:
        return False


def ping_sweep(subnet_prefix: str, workers: int = 64) -> None:
    """Wake the ARP cache for every host on subnet_prefix.x.0/24."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda i: _ping(f"{subnet_prefix}.{i}"), range(1, 255)))


def detect_subnet_prefix() -> str | None:
    """Best-effort LAN subnet detection: Windows ipconfig under WSL,
    else the native Linux default route's source address."""
    if _ARP_EXE.exists():
        out = subprocess.run(
            [str(_ARP_EXE).replace("ARP.EXE", "ipconfig.exe")], capture_output=True, text=True
        ).stdout
        for m in re.finditer(
            r"IPv4 Address[^\d]*(\d+\.\d+\.\d+\.\d+)[\s\S]{0,120}?Subnet Mask[^\d]*(\d+\.\d+\.\d+\.\d+)",
            out,
        ):
            ip, mask = m.groups()
            if ip.startswith(("169.254.", "127.")):
                continue
            if mask != "255.255.255.0":  # only /24 handled; use config.subnet otherwise
                continue
            return ".".join(ip.split(".")[:3])
        return None
    try:
        out = subprocess.run(
            ["ip", "-4", "route", "get", "1.1.1.1"], capture_output=True, text=True
        ).stdout
        m = re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return ".".join(m.group(1).split(".")[:3])
    except OSError:
        pass
    return None


def resolve_ip(mac: str, hint_ip: str | None = None, subnet_prefix: str | None = None) -> str | None:
    """Find the current IP for `mac`. Fast path: hint IP still owns the MAC."""
    if hint_ip and _ping(hint_ip):
        entry = next(
            (line for line in arp_table().splitlines() if hint_ip in line), ""
        )
        if _norm_mac(mac) in entry.lower().replace("-", ":"):
            return hint_ip
    prefix = subnet_prefix or detect_subnet_prefix()
    if prefix is None:
        return None
    ping_sweep(prefix)
    return find_ip_by_mac(mac, arp_table())
