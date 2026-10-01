"""Kişisel portföy için basit SQLite deposu (tek kullanıcı, yerel kullanım)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from ..core.settings import DB_PATH
from .models import Position

_SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_code TEXT NOT NULL,
    label TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""


@contextmanager
def _connect(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.execute(_SCHEMA)


def _row_to_position(row: sqlite3.Row) -> Position:
    return Position(
        id=row["id"],
        instrument_code=row["instrument_code"],
        label=row["label"],
        category=row["category"],
        quantity=row["quantity"],
        unit_cost=row["unit_cost"],
        purchase_date=date.fromisoformat(row["purchase_date"]),
        note=row["note"] or "",
    )


def add_position(position: Position, db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO positions
                (instrument_code, label, category, quantity, unit_cost, purchase_date, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.instrument_code,
                position.label,
                position.category,
                position.quantity,
                position.unit_cost,
                position.purchase_date.isoformat(),
                position.note,
            ),
        )
        return int(cur.lastrowid)


def list_positions(db_path: Path = DB_PATH) -> list[Position]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM positions ORDER BY purchase_date DESC, id DESC").fetchall()
    return [_row_to_position(row) for row in rows]


def delete_position(position_id: int, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM positions WHERE id = ?", (position_id,))


def update_position(position: Position, db_path: Path = DB_PATH) -> None:
    if position.id is None:
        raise ValueError("Güncellenecek pozisyonun id'si olmalı.")
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE positions
            SET instrument_code = ?, label = ?, category = ?, quantity = ?,
                unit_cost = ?, purchase_date = ?, note = ?
            WHERE id = ?
            """,
            (
                position.instrument_code,
                position.label,
                position.category,
                position.quantity,
                position.unit_cost,
                position.purchase_date.isoformat(),
                position.note,
                position.id,
            ),
        )
