import json
import sqlite3
from pathlib import Path

from app.audit.models import CompanyDataAudit
from app.history.models import ScoreHistoryEntry
from app.portfolio.models import PortfolioPosition
from app.scoring.models import FinancialMetrics, ScoreBreakdown
from app.watchlist.models import WatchlistEntry
from app.sector.profiles import CompanyProfile, detect_company_profile

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
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(companies)").fetchall()
        }
        sector_columns = {
            "company_profile": "TEXT NOT NULL DEFAULT 'standard'",
            "capital_adequacy_ratio": "REAL",
            "npl_ratio": "REAL",
            "loan_to_deposit_ratio": "REAL",
            "net_interest_margin": "REAL",
            "cost_income_ratio": "REAL",
            "premium_growth": "REAL",
            "combined_ratio": "REAL",
            "solvency_ratio": "REAL",
            "nav_discount": "REAL",
            "occupancy_rate": "REAL",
        }
        for column, definition in sector_columns.items():
            if column not in existing_columns:
                conn.execute(
                    f"ALTER TABLE companies ADD COLUMN {column} {definition}"
                )
        for row in conn.execute(
            "SELECT symbol, company_name, company_profile FROM companies"
        ).fetchall():
            detected = detect_company_profile(row["company_name"])
            if (
                row["company_profile"] == CompanyProfile.STANDARD.value
                and detected != CompanyProfile.STANDARD
            ):
                conn.execute(
                    "UPDATE companies SET company_profile=? WHERE symbol=?",
                    (detected.value, row["symbol"]),
                )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS watchlist(
            symbol TEXT PRIMARY KEY,
            note TEXT NOT NULL DEFAULT '',
            target_alpha_score REAL NOT NULL DEFAULT 80,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(symbol) REFERENCES companies(symbol))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS score_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            total_score REAL NOT NULL,
            grade TEXT NOT NULL,
            decision TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(symbol) REFERENCES companies(symbol))"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_score_history_symbol_id
            ON score_history(symbol, id)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS portfolio_positions(
            symbol TEXT PRIMARY KEY,
            quantity REAL NOT NULL,
            average_cost REAL NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(symbol) REFERENCES companies(symbol))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS company_data_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            source_type TEXT NOT NULL,
            company_profile TEXT NOT NULL,
            period_months INTEGER,
            report_period_end TEXT,
            financial_report_name TEXT NOT NULL DEFAULT '',
            activity_report_name TEXT NOT NULL DEFAULT '',
            financial_report_hash TEXT NOT NULL DEFAULT '',
            activity_report_hash TEXT NOT NULL DEFAULT '',
            financial_report_scale REAL NOT NULL DEFAULT 1,
            comparison_period_end TEXT,
            comparison_period_confirmed INTEGER NOT NULL DEFAULT 0,
            completeness REAL NOT NULL,
            alpha_score REAL NOT NULL,
            grade TEXT NOT NULL DEFAULT '',
            decision TEXT NOT NULL DEFAULT '',
            confidence_score REAL,
            confidence_status TEXT NOT NULL DEFAULT '',
            methodology_version TEXT NOT NULL DEFAULT 'legacy',
            input_fingerprint TEXT NOT NULL DEFAULT '',
            score_breakdown TEXT NOT NULL DEFAULT '{}',
            field_sources TEXT NOT NULL DEFAULT '{}',
            source_values TEXT NOT NULL DEFAULT '{}',
            metric_values TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(symbol) REFERENCES companies(symbol))"""
        )
        audit_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(company_data_audit)"
            ).fetchall()
        }
        audit_migrations = {
            "report_period_end": "TEXT",
            "field_sources": "TEXT NOT NULL DEFAULT '{}'",
            "grade": "TEXT NOT NULL DEFAULT ''",
            "decision": "TEXT NOT NULL DEFAULT ''",
            "confidence_score": "REAL",
            "confidence_status": "TEXT NOT NULL DEFAULT ''",
            "methodology_version": "TEXT NOT NULL DEFAULT 'legacy'",
            "input_fingerprint": "TEXT NOT NULL DEFAULT ''",
            "score_breakdown": "TEXT NOT NULL DEFAULT '{}'",
            "source_values": "TEXT NOT NULL DEFAULT '{}'",
            "metric_values": "TEXT NOT NULL DEFAULT '{}'",
            "financial_report_hash": "TEXT NOT NULL DEFAULT ''",
            "activity_report_hash": "TEXT NOT NULL DEFAULT ''",
            "financial_report_scale": "REAL NOT NULL DEFAULT 1",
            "comparison_period_end": "TEXT",
            "comparison_period_confirmed": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, definition in audit_migrations.items():
            if column not in audit_columns:
                conn.execute(
                    f"ALTER TABLE company_data_audit ADD COLUMN {column} {definition}"
                )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_company_data_audit_symbol_id
            ON company_data_audit(symbol, id)"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_company_data_audit_financial_hash
            ON company_data_audit(financial_report_hash)"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_company_data_audit_activity_hash
            ON company_data_audit(activity_report_hash)"""
        )

def upsert_company(m):
    d = m.model_dump(mode="json")
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


def add_score_history(symbol: str, score: ScoreBreakdown) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO score_history(symbol, total_score, grade, decision)
            VALUES(?, ?, ?, ?)""",
            (
                symbol.upper().strip(),
                score.total,
                score.grade,
                score.decision,
            ),
        )


def list_score_history(
    symbol: str,
    limit: int = 20,
) -> list[ScoreHistoryEntry]:
    safe_limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, symbol, total_score, grade, decision, created_at
            FROM score_history
            WHERE symbol=?
            ORDER BY id DESC
            LIMIT ?""",
            (symbol.upper().strip(), safe_limit),
        ).fetchall()
    return [ScoreHistoryEntry(**dict(row)) for row in reversed(rows)]


def add_company_data_audit(audit: CompanyDataAudit) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO company_data_audit(
            symbol, source_type, company_profile, period_months, report_period_end,
            financial_report_name, activity_report_name,
            financial_report_hash, activity_report_hash,
            financial_report_scale, comparison_period_end,
            comparison_period_confirmed, completeness,
            alpha_score, grade, decision, confidence_score, confidence_status,
            methodology_version, input_fingerprint, score_breakdown,
            field_sources, source_values, metric_values)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                audit.symbol.upper().strip(),
                audit.source_type.value,
                audit.company_profile.value,
                audit.period_months,
                (
                    audit.report_period_end.isoformat()
                    if audit.report_period_end
                    else None
                ),
                audit.financial_report_name,
                audit.activity_report_name,
                audit.financial_report_hash,
                audit.activity_report_hash,
                audit.financial_report_scale,
                (
                    audit.comparison_period_end.isoformat()
                    if audit.comparison_period_end
                    else None
                ),
                int(audit.comparison_period_confirmed),
                audit.completeness,
                audit.alpha_score,
                audit.grade,
                audit.decision,
                audit.confidence_score,
                audit.confidence_status,
                audit.methodology_version,
                audit.input_fingerprint,
                json.dumps(audit.score_breakdown, sort_keys=True),
                json.dumps(
                    {
                        field: source.value
                        for field, source in audit.field_sources.items()
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                json.dumps(
                    audit.source_values,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                json.dumps(
                    audit.metric_values,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )


def _audit_from_row(row: sqlite3.Row) -> CompanyDataAudit:
    values = dict(row)
    values["field_sources"] = json.loads(values.get("field_sources") or "{}")
    values["score_breakdown"] = json.loads(
        values.get("score_breakdown") or "{}"
    )
    values["source_values"] = json.loads(
        values.get("source_values") or "{}"
    )
    values["metric_values"] = json.loads(
        values.get("metric_values") or "{}"
    )
    return CompanyDataAudit(**values)


def get_latest_company_data_audit(symbol: str) -> CompanyDataAudit | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT id, symbol, source_type, company_profile, period_months,
            report_period_end,
            financial_report_name, activity_report_name,
            financial_report_hash, activity_report_hash,
            financial_report_scale, comparison_period_end,
            comparison_period_confirmed, completeness,
            alpha_score, grade, decision, confidence_score,
            confidence_status, methodology_version, input_fingerprint,
            score_breakdown,
            field_sources, source_values, metric_values, created_at
            FROM company_data_audit
            WHERE symbol=? ORDER BY id DESC LIMIT 1""",
            (symbol.upper().strip(),),
        ).fetchone()
    return _audit_from_row(row) if row else None


def list_company_data_audits(
    symbol: str,
    limit: int = 20,
) -> list[CompanyDataAudit]:
    safe_limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, symbol, source_type, company_profile, period_months,
            report_period_end,
            financial_report_name, activity_report_name,
            financial_report_hash, activity_report_hash,
            financial_report_scale, comparison_period_end,
            comparison_period_confirmed, completeness,
            alpha_score, grade, decision, confidence_score,
            confidence_status, methodology_version, input_fingerprint,
            score_breakdown,
            field_sources, source_values, metric_values, created_at
            FROM company_data_audit
            WHERE symbol=? ORDER BY id DESC LIMIT ?""",
            (symbol.upper().strip(), safe_limit),
        ).fetchall()
    return [_audit_from_row(row) for row in reversed(rows)]


def list_latest_company_data_audits() -> list[CompanyDataAudit]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT audit.id, audit.symbol, audit.source_type,
            audit.company_profile, audit.period_months,
            audit.report_period_end,
            audit.financial_report_name, audit.activity_report_name,
            audit.financial_report_hash, audit.activity_report_hash,
            audit.financial_report_scale,
            audit.comparison_period_end, audit.comparison_period_confirmed,
            audit.completeness, audit.alpha_score, audit.grade,
            audit.decision, audit.confidence_score, audit.confidence_status,
            audit.methodology_version, audit.input_fingerprint,
            audit.score_breakdown,
            audit.field_sources, audit.source_values, audit.metric_values,
            audit.created_at
            FROM company_data_audit AS audit
            INNER JOIN (
                SELECT symbol, MAX(id) AS latest_id
                FROM company_data_audit GROUP BY symbol
            ) AS latest ON latest.latest_id = audit.id
            ORDER BY audit.symbol"""
        ).fetchall()
    return [_audit_from_row(row) for row in rows]


def list_document_usages(
    document_hash: str,
    limit: int = 100,
) -> list[CompanyDataAudit]:
    if not document_hash:
        return []
    safe_limit = max(1, min(limit, 500))
    with connect() as conn:
        rows = conn.execute(
            """SELECT id, symbol, source_type, company_profile, period_months,
            report_period_end,
            financial_report_name, activity_report_name,
            financial_report_hash, activity_report_hash,
            financial_report_scale, comparison_period_end,
            comparison_period_confirmed, completeness,
            alpha_score, grade, decision, confidence_score,
            confidence_status, methodology_version, input_fingerprint,
            score_breakdown, field_sources, source_values, metric_values,
            created_at
            FROM company_data_audit
            WHERE financial_report_hash=? OR activity_report_hash=?
            ORDER BY id DESC LIMIT ?""",
            (document_hash, document_hash, safe_limit),
        ).fetchall()
    return [_audit_from_row(row) for row in rows]


def upsert_portfolio_position(position: PortfolioPosition) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO portfolio_positions(symbol, quantity, average_cost)
            VALUES(?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
            quantity=excluded.quantity,
            average_cost=excluded.average_cost,
            updated_at=CURRENT_TIMESTAMP""",
            (position.symbol, position.quantity, position.average_cost),
        )


def remove_portfolio_position(symbol: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM portfolio_positions WHERE symbol=?",
            (symbol.upper().strip(),),
        )


def list_portfolio_positions() -> list[PortfolioPosition]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT symbol, quantity, average_cost
            FROM portfolio_positions ORDER BY updated_at, symbol"""
        ).fetchall()
    return [PortfolioPosition(**dict(row)) for row in rows]


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
