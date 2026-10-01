from datetime import date

import pytest

from pm.portfolio.models import Position
from pm.portfolio.store import add_position, delete_position, list_positions, update_position


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "portfoy_test.db"


def _position(**overrides):
    defaults = dict(
        instrument_code="THYAO",
        label="THYAO",
        category="Hisse (BIST)",
        quantity=10.0,
        unit_cost=200.0,
        purchase_date=date(2024, 1, 1),
        note="",
    )
    defaults.update(overrides)
    return Position(**defaults)


def test_add_and_list_position(db_path):
    add_position(_position(), db_path=db_path)
    positions = list_positions(db_path=db_path)
    assert len(positions) == 1
    assert positions[0].instrument_code == "THYAO"
    assert positions[0].quantity == 10.0
    assert positions[0].id is not None


def test_delete_position(db_path):
    pos_id = add_position(_position(), db_path=db_path)
    delete_position(pos_id, db_path=db_path)
    assert list_positions(db_path=db_path) == []


def test_update_position(db_path):
    pos_id = add_position(_position(), db_path=db_path)
    updated = _position(id=pos_id, quantity=25.0, note="güncellendi")
    update_position(updated, db_path=db_path)
    positions = list_positions(db_path=db_path)
    assert positions[0].quantity == 25.0
    assert positions[0].note == "güncellendi"


def test_update_without_id_raises(db_path):
    with pytest.raises(ValueError):
        update_position(_position(), db_path=db_path)


def test_cost_basis_property():
    pos = _position(quantity=4.0, unit_cost=50.0)
    assert pos.cost_basis == 200.0
