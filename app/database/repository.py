import sqlite3
from pathlib import Path

from app.scoring.models import FinancialMetrics
from app.watchlist.models import WatchlistEntry

DB_PATH = Path(__file__).resolve().parents[2] / 'data' / 'alphabist.db'

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    sql = """CREATE TABLE IF NOT EXISTS companies(
    symbol TEXT PRIMARY KEY, company_name TEXT, revenue_growth REAL,
    net_profit_growth REAL, net_margin REAL, roe REAL, debt_to_equity REAL,
    current_ratio REAL, operating_cash_flow REAL, free_cash_flow REAL,
    asset_turnover REAL, valuation_score_input REAL,
    management_score_input REAL, risk_score_input REAL)"""
    with connect() as conn:
        conn.execute(sql)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS watchlist(
            symbol TEXT PRIMARY KEY,
            note TEXT NOT NULL DEFAULT '',
            target_alpha_score REAL NOT NULL DEFAULT 80,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(symbol) REFERENCES companies(symbol))"""
        )

def upsert_company(m):
    d = m.model_dump()
    columns = ','.join(d)
    placeholders = ','.join('?' for _ in d)
    updates = ','.join(f'{k}=excluded.{k}' for k in d if k != 'symbol')
    sql = f'INSERT INTO companies({columns}) VALUES({placeholders}) ON CONFLICT(symbol) DO UPDATE SET {updates}'
    with connect() as conn:
        conn.execute(sql, tuple(d.values()))

def list_companies():
    with connect() as conn:
        rows = conn.execute('SELECT * FROM companies ORDER BY symbol').fetchall()
    return [FinancialMetrics(**dict(row)) for row in rows]

def get_company(symbol):
    with connect() as conn:
        row = conn.execute('SELECT * FROM companies WHERE symbol=?', (symbol.upper(),)).fetchone()
    return FinancialMetrics(**dict(row)) if row else None


def upsert_watchlist_entry(entry: WatchlistEntry) -> None:
    sql = """INSERT INTO watchlist(symbol, note, target_alpha_score)
    VALUES(?, ?, ?)
    ON CONFLICT(symbol) DO UPDATE SET
    note=excluded.note,
    target_alpha_score=excluded.target_alpha_score"""
    with connect() as conn:
        conn.execute(sql, (entry.symbol, entry.note, entry.target_alpha_score))


def remove_watchlist_entry(symbol: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM watchlist WHERE symbol=?",
            (symbol.upper().strip(),),
        )


def list_watchlist_entries() -> list[WatchlistEntry]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT symbol, note, target_alpha_score
            FROM watchlist ORDER BY created_at, symbol"""
        ).fetchall()
    return [WatchlistEntry(**dict(row)) for row in rows]

def seed_demo_data():
    if list_companies():
        return
    demos = [
        FinancialMetrics(symbol='AKSA', company_name='Aksa Akrilik Kimya Sanayii A.Ş.', revenue_growth=18.6, net_profit_growth=133, net_margin=6.3, roe=12, debt_to_equity=1.21, current_ratio=.89, operating_cash_flow=3710870000, free_cash_flow=2838810000, asset_turnover=.56, valuation_score_input=80, management_score_input=90, risk_score_input=72),
        FinancialMetrics(symbol='GUBRF', company_name='Gübre Fabrikaları Türk A.Ş.', revenue_growth=23.3, net_profit_growth=278, net_margin=13.7, roe=29, debt_to_equity=.70, current_ratio=1.62, operating_cash_flow=3041861883, free_cash_flow=1218068850, asset_turnover=1.25, valuation_score_input=78, management_score_input=88, risk_score_input=65)
    ]
    for item in demos:
        upsert_company(item)
