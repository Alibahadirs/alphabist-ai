import sys
import types

import pytest

from pm.alerts import mailer


def test_load_app_password_prefers_cloud_env_var(monkeypatch):
    monkeypatch.setenv("PORTFOY_GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    assert mailer.load_app_password("a@gmail.com") == "abcdefghijklmnop"


def test_load_app_password_falls_back_to_keyring(monkeypatch):
    monkeypatch.delenv("PORTFOY_GMAIL_APP_PASSWORD", raising=False)
    fake_keyring = types.SimpleNamespace(get_password=lambda service, sender: "secret123456789a")
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
    assert mailer.load_app_password("a@gmail.com") == "secret123456789a"


def test_save_app_password_strips_spaces_and_uses_service_name(monkeypatch):
    calls = []
    fake_keyring = types.SimpleNamespace(set_password=lambda service, sender, password: calls.append((service, sender, password)))
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    mailer.save_app_password("a@gmail.com", "abcd efgh ijkl mnop")

    assert calls == [(mailer.KEYRING_SERVICE, "a@gmail.com", "abcdefghijklmnop")]


def test_send_alert_email_raises_without_password(monkeypatch):
    monkeypatch.delenv("PORTFOY_GMAIL_APP_PASSWORD", raising=False)
    fake_keyring = types.SimpleNamespace(get_password=lambda service, sender: None)
    monkeypatch.setitem(sys.modules, "keyring", fake_keyring)

    with pytest.raises(RuntimeError):
        mailer.send_alert_email(
            sender="a@gmail.com", recipient="b@gmail.com", subject="x", html_body="<p>x</p>"
        )
