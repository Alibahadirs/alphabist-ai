import pytest

from pm.alerts.config import AlertConfig, load_config, save_config


def test_save_and_load_round_trip(tmp_path):
    config_path = tmp_path / "daily_alert_config.json"
    original = AlertConfig(sender="a@gmail.com", recipient="b@gmail.com", extra_codes=("THYAO", "USDTRY"))
    save_config(original, config_path=config_path)

    loaded = load_config(config_path=config_path)
    assert loaded == original


def test_load_missing_file_raises(tmp_path):
    config_path = tmp_path / "missing.json"
    with pytest.raises(RuntimeError):
        load_config(config_path=config_path)


def test_load_prefers_cloud_env_vars(tmp_path, monkeypatch):
    config_path = tmp_path / "daily_alert_config.json"
    save_config(AlertConfig(sender="local@gmail.com", recipient="local2@gmail.com"), config_path=config_path)

    monkeypatch.setenv("PORTFOY_GMAIL_SENDER", "cloud@gmail.com")
    monkeypatch.setenv("PORTFOY_REPORT_RECIPIENT", "cloud2@gmail.com")
    monkeypatch.setenv("PORTFOY_WATCH_CODES", "garan, thyao")

    loaded = load_config(config_path=config_path)
    assert loaded.sender == "cloud@gmail.com"
    assert loaded.recipient == "cloud2@gmail.com"
    assert loaded.extra_codes == ("GARAN", "THYAO")


def test_save_creates_parent_directory(tmp_path):
    config_path = tmp_path / "nested" / "daily_alert_config.json"
    save_config(AlertConfig(sender="a@gmail.com", recipient="b@gmail.com"), config_path=config_path)
    assert config_path.exists()
