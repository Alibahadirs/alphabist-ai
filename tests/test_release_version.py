from app.core.settings import settings


def test_release_version_is_1_21_0():
    assert settings.app_version == "1.21.0"
