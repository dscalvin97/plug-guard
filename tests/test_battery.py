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
