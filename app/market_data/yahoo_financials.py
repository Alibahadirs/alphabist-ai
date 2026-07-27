from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import yfinance as yf

from app.parser.models import FinancialReportDraft
from app.sector.profiles import detect_company_profile


@dataclass(frozen=True)
class YahooFinancialResult:
    draft: FinancialReportDraft
    yahoo_symbol: str
    current_period: date
    comparison_period: date | None
    warnings: list[str]


def _statement_value(
    frame: pd.DataFrame,
    period: pd.Timestamp,
    *row_names: str,
) -> float | None:
    if frame.empty or period not in frame.columns:
        return None
    for row_name in row_names:
        if row_name in frame.index:
            value = frame.at[row_name, period]
            if pd.notna(value):
                return float(value)
    return None


def _comparison_period(columns: pd.Index, current: pd.Timestamp) -> pd.Timestamp | None:
    candidates = [pd.Timestamp(value) for value in columns if pd.Timestamp(value) < current]
    if not candidates:
        return None
    target = current - pd.DateOffset(years=1)
    return min(candidates, key=lambda value: abs((value - target).days))


def fetch_yahoo_financials(symbol: str) -> YahooFinancialResult:
    normalized = symbol.upper().strip().removesuffix(".IS")
    if not normalized or not normalized.isalnum() or not 3 <= len(normalized) <= 6:
        raise ValueError("Geçerli bir BIST hisse kodu girin.")
    yahoo_symbol = f"{normalized}.IS"
    ticker = yf.Ticker(yahoo_symbol)
    income = ticker.get_income_stmt(freq="quarterly")
    balance = ticker.get_balance_sheet(freq="quarterly")
    cash_flow = ticker.get_cash_flow(freq="quarterly")
    if income.empty or balance.empty:
        raise RuntimeError("Yahoo Finance üç aylık finansal tabloları döndürmedi.")

    common_periods = sorted(
        set(pd.Timestamp(value) for value in income.columns)
        & set(pd.Timestamp(value) for value in balance.columns),
        reverse=True,
    )
    if not common_periods:
        raise RuntimeError("Gelir tablosu ile bilançoda ortak dönem bulunamadı.")
    current = common_periods[0]
    previous = _comparison_period(income.columns, current)
    previous_balance = _comparison_period(balance.columns, current)
    info = ticker.get_info() or {}
    company_name = str(info.get("longName") or info.get("shortName") or normalized)

    draft = FinancialReportDraft(
        symbol=normalized,
        company_name=company_name,
        period_months=3,
        report_period_end=current.date(),
        company_profile=detect_company_profile(company_name),
        revenue=_statement_value(income, current, "TotalRevenue", "OperatingRevenue"),
        previous_revenue=(
            _statement_value(income, previous, "TotalRevenue", "OperatingRevenue")
            if previous is not None else None
        ),
        net_profit=_statement_value(
            income, current, "NetIncomeCommonStockholders", "NetIncome"
        ),
        previous_net_profit=(
            _statement_value(
                income, previous, "NetIncomeCommonStockholders", "NetIncome"
            ) if previous is not None else None
        ),
        equity=_statement_value(
            balance, current, "StockholdersEquity", "TotalEquityGrossMinorityInterest"
        ),
        previous_equity=(
            _statement_value(
                balance, previous_balance,
                "StockholdersEquity", "TotalEquityGrossMinorityInterest",
            ) if previous_balance is not None else None
        ),
        total_debt=_statement_value(balance, current, "TotalDebt"),
        cash=_statement_value(
            balance, current,
            "CashCashEquivalentsAndShortTermInvestments", "CashAndCashEquivalents",
        ),
        current_assets=_statement_value(balance, current, "CurrentAssets"),
        current_liabilities=_statement_value(balance, current, "CurrentLiabilities"),
        total_assets=_statement_value(balance, current, "TotalAssets"),
        previous_total_assets=(
            _statement_value(balance, previous_balance, "TotalAssets")
            if previous_balance is not None else None
        ),
        operating_cash_flow=(
            _statement_value(cash_flow, current, "OperatingCashFlow")
            if current in cash_flow.columns else None
        ),
        capital_expenditures=(
            _statement_value(cash_flow, current, "CapitalExpenditure")
            if current in cash_flow.columns else None
        ),
    )
    required = {
        "revenue": draft.revenue,
        "previous_revenue": draft.previous_revenue,
        "net_profit": draft.net_profit,
        "previous_net_profit": draft.previous_net_profit,
        "equity": draft.equity,
        "total_assets": draft.total_assets,
    }
    missing = [name for name, value in required.items() if value is None]
    warnings = []
    if missing:
        warnings.append("Yahoo Finance bazı temel finansal alanları sağlamadı: " + ", ".join(missing))
    warnings.append(
        "Yahoo Finance resmi KAP kaynağı değildir; kaydetmeden önce dönem ve tutarları kontrol edin."
    )
    return YahooFinancialResult(
        draft=draft,
        yahoo_symbol=yahoo_symbol,
        current_period=current.date(),
        comparison_period=previous.date() if previous is not None else None,
        warnings=warnings,
    )
