from app.core.settings import settings


def test_release_version_is_1_20_0():
    assert settings.app_version == "1.20.0"
