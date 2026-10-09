from plug_guard.battery import BatteryState
from plug_guard.controller import Controller
import pytest


def make(pct, ac=False, charging=False, status="Discharging"):
    return BatteryState(percent=pct, charging=charging, ac_online=ac, status=status)


c = Controller(turn_on_below=20, turn_off_above=90)


@pytest.mark.parametrize("pct,expected_on", [(0, True), (10, True), (20, True), (21, None), (50, None)])
def test_unplugged_hysteresis(pct, expected_on):
    assert c.decide(make(pct)).turn_on is expected_on


@pytest.mark.parametrize("pct", [50, 89])
def test_charging_holds(pct):
    assert c.decide(make(pct, ac=True, charging=True, status="Charging")).turn_on is None


@pytest.mark.parametrize("pct", [90, 100])
def test_charged_turns_off(pct):
    d = c.decide(make(pct, ac=True, charging=False, status="Full"))
    assert d.turn_on is False


def test_full_on_ac_turns_off_even_below_threshold_band():
    # e.g. laptop full at 100% but unplugged later shouldn't matter; this is AC-full case
    d = c.decide(make(80, ac=True, status="Full"))
    assert d.turn_on is False


def test_unknown_percent_holds():
    assert c.decide(make(None)).turn_on is None


def test_threshold_validation():
    with pytest.raises(ValueError):
        Controller(turn_on_below=90, turn_off_above=20)
