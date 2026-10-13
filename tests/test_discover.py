from plug_guard.discover import find_ip_by_mac, _norm_mac

# Verbatim `arp -a` output shape from Windows 11 (the WSL execution path)
WIN_ARP = """
Interface: 192.168.1.54 --- 0x5
  Internet Address      Physical Address      Type
  192.168.1.1           00-11-22-33-44-55     dynamic
  192.168.1.70          80-64-7c-89-3d-a0     dynamic
  224.0.0.22            01-00-5e-00-00-16     static
"""

# `ip neigh` shape (native Linux path)
LINUX_NEIGH = """
192.168.1.70 dev eth0 lladdr 80:64:7c:89:3d:a0 REACHABLE
192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff STALE
"""


def test_finds_windows_arp_entry():
    assert find_ip_by_mac("80:64:7c:89:3d:a0", WIN_ARP) == "192.168.1.70"


def test_mac_format_tolerance():
    # user-supplied MAC may be dashed/uppercase
    assert find_ip_by_mac("80-64-7C-89-3D-A0", WIN_ARP) == "192.168.1.70"
    assert find_ip_by_mac("8064.7c89.3da0", LINUX_NEIGH) is None  # cisco format not in arp dump


def test_finds_linux_neigh_entry():
    assert find_ip_by_mac("80:64:7c:89:3d:a0", LINUX_NEIGH) == "192.168.1.70"


def test_absent_mac_returns_none():
    assert find_ip_by_mac("de:ad:be:ef:00:01", WIN_ARP) is None


def test_subnet_filter_drops_stale_other_interface():
    # regression: a stale ARP entry from another interface (home WiFi) must not
    # leak through when discovery is pinned to a specific subnet (e.g. hotspot)
    assert find_ip_by_mac("80:64:7c:89:3d:a0", WIN_ARP, subnet_prefix="192.168.1") == "192.168.1.70"
    assert find_ip_by_mac("80:64:7c:89:3d:a0", WIN_ARP, subnet_prefix="192.168.137") is None
    # no subnet given -> no filtering (old behavior)
    assert find_ip_by_mac("80:64:7c:89:3d:a0", WIN_ARP) == "192.168.1.70"


def test_norm_mac():
    assert _norm_mac("80-64-7C-89-3D-A0") == "80:64:7c:89:3d:a0"
