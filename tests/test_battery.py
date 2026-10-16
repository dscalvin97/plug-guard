from plug_guard.battery import read_sysfs


def write(p, v):
    p.write_text(v)


def make_sysfs(tmp, bat_status="Discharging", capacity="42", ac_online="0", with_battery=True):
    root = tmp / "ps"
    (root).mkdir()
    if with_battery:
        bat = root / "BAT0"
        bat.mkdir()
        write(bat / "type", "Battery")
        write(bat / "status", bat_status)
        write(bat / "capacity", capacity)
    ac = root / "AC0"
    ac.mkdir()
    write(ac / "type", "Mains")
    write(ac / "online", ac_online)
    return root


def test_reads_discharging(tmp_path):
    s = read_sysfs(make_sysfs(tmp_path, "Discharging", "42", "0"))
    assert (s.percent, s.charging, s.ac_online, s.status) == (42, False, False, "Discharging")


def test_reads_charging_on_ac(tmp_path):
    s = read_sysfs(make_sysfs(tmp_path, "Charging", "55", "1"))
    assert (s.percent, s.charging, s.ac_online) == (55, True, True)


def test_no_battery_returns_none(tmp_path):
    assert read_sysfs(make_sysfs(tmp_path, with_battery=False)) is None


def test_missing_dir_returns_none(tmp_path):
    assert read_sysfs(tmp_path / "nope") is None


def make_two_batteries(tmp, cap0, status0, cap1, status1, ac_online="0"):
    root = tmp / "ps"
    root.mkdir()
    for name, cap, status in (("BAT0", cap0, status0), ("BAT1", cap1, status1)):
        if cap is None:
            continue
        bat = root / name
        bat.mkdir()
        write(bat / "type", "Battery")
        write(bat / "status", status)
        write(bat / "capacity", cap)
    ac = root / "AC0"
    ac.mkdir()
    write(ac / "type", "Mains")
    write(ac / "online", ac_online)
    return root


def test_multi_battery_picks_lowest(tmp_path):
    # BAT0 says 55% charging, BAT1 says 10% discharging -> the drained pack is
    # the honest "needs charge" signal, so 10% must win or the plug never turns on.
    s = read_sysfs(make_two_batteries(tmp_path, "55", "Charging", "10", "Discharging"))
    assert s.percent == 10
    assert s.status == "Discharging"


def test_multi_battery_charging_if_any_charging(tmp_path):
    # charging is true if ANY pack reports Charging
    s = read_sysfs(make_two_batteries(tmp_path, "10", "Discharging", "55", "Charging"))
    assert s.percent == 10
    assert s.charging is True


def test_multi_battery_ignores_missing_capacity_file(tmp_path):
    # a BAT entry without a readable capacity must not crash the read
    s = read_sysfs(make_two_batteries(tmp_path, None, None, "42", "Discharging"))
    assert s.percent == 42
