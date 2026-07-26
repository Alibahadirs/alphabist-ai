from app.core.settings import settings


def test_release_version_is_1_23_2():
    assert settings.app_version == "1.23.2"
