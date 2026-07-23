from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCREEN_COUNT = 12


@pytest.mark.parametrize("page_index", range(SCREEN_COUNT))
def test_every_navigation_screen_renders_without_exception(page_index):
    app = AppTest.from_file(str(PROJECT_ROOT / "main.py"))
    app.run(timeout=30)

    navigation = app.sidebar.radio[0]
    assert len(navigation.options) == SCREEN_COUNT
    navigation.set_value(navigation.options[page_index])
    app.run(timeout=30)

    assert not app.exception
