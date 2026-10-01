import datetime

from pm.alerts import runner


class _FakeConfig:
    sender = "a@gmail.com"
    recipient = "b@gmail.com"
    extra_codes = ()


class _FakeResult:
    generated_at = datetime.datetime(2024, 1, 1, 12, 0)
    actionable = ()
    errors = ()
    evaluated = 0
    requested = 0


def test_dry_run_does_not_send_email(monkeypatch):
    monkeypatch.setattr(runner, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(runner, "run_daily_scan", lambda extra_codes: _FakeResult())
    sent = []
    monkeypatch.setattr(runner, "send_alert_email", lambda **kwargs: sent.append(kwargs))

    exit_code = runner.main(["--dry-run", "--force"])

    assert exit_code == 0
    assert sent == []


def test_normal_run_sends_email_with_expected_args(monkeypatch):
    monkeypatch.setattr(runner, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(runner, "run_daily_scan", lambda extra_codes: _FakeResult())
    sent = []
    monkeypatch.setattr(runner, "send_alert_email", lambda **kwargs: sent.append(kwargs))

    exit_code = runner.main(["--force"])

    assert exit_code == 0
    assert len(sent) == 1
    assert sent[0]["sender"] == "a@gmail.com"
    assert sent[0]["recipient"] == "b@gmail.com"
    assert sent[0]["csv_bytes"] == b""


def test_weekend_skips_without_force(monkeypatch):
    class _Saturday(datetime.date):
        @classmethod
        def today(cls):
            return cls(2024, 1, 6)  # bilinen bir Cumartesi

    monkeypatch.setattr(runner, "date", _Saturday)
    sent = []
    monkeypatch.setattr(runner, "send_alert_email", lambda **kwargs: sent.append(kwargs))
    monkeypatch.setattr(runner, "load_config", lambda: _FakeConfig())
    monkeypatch.setattr(runner, "run_daily_scan", lambda extra_codes: _FakeResult())

    exit_code = runner.main([])

    assert exit_code == 0
    assert sent == []
