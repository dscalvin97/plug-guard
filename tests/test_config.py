import json

import pytest

from plug_guard.config import Config


def write_cfg(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(data if isinstance(data, str) else json.dumps(data))
    return p


def test_corrupt_json_raises_clean_exit(tmp_path):
    # a hand-edit typo must give a clear message, not a raw traceback
    with pytest.raises(SystemExit, match="not valid JSON"):
        Config.load(write_cfg(tmp_path, "{ device_id: broken"))


def test_non_object_json_raises(tmp_path):
    with pytest.raises(SystemExit, match="JSON object"):
        Config.load(write_cfg(tmp_path, "[1, 2, 3]"))


def test_poll_interval_string_coerced(tmp_path):
    cfg = Config.load(write_cfg(tmp_path, {"dry_run": True, "poll_interval": "60"}))
    assert cfg.poll_interval == 60


def test_poll_interval_zero_floored_to_one(tmp_path):
    # Event.wait(0) would busy-loop the run loop; floor to 1s
    cfg = Config.load(write_cfg(tmp_path, {"dry_run": True, "poll_interval": 0}))
    assert cfg.poll_interval == 1


def test_poll_interval_negative_floored(tmp_path):
    cfg = Config.load(write_cfg(tmp_path, {"dry_run": True, "poll_interval": -5}))
    assert cfg.poll_interval == 1


def test_poll_interval_garbage_raises(tmp_path):
    with pytest.raises(SystemExit, match="poll_interval"):
        Config.load(write_cfg(tmp_path, {"dry_run": True, "poll_interval": "soon"}))


def test_valid_minimal_dry_run(tmp_path):
    cfg = Config.load(write_cfg(tmp_path, {"dry_run": True}))
    assert cfg.dry_run is True
