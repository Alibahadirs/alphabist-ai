from datetime import date

import pytest

from app.parser.converter import to_financial_metrics
from app.parser.extractor import extract_financial_report
from app.sector.profiles import CompanyProfile
from app.validation.service import validate_financial_metrics


COMMON_HEADER = """
BIST: {symbol}
31.03.2026 31.03.2025
Tutarlar aksi belirtilmedikçe bin Türk Lirası olarak ifade edilmiştir.
"""


def _extract(monkeypatch, text: str, symbol: str):
    monkeypatch.setattr(
        "app.parser.extractor._read_pdf",
        lambda _file_bytes: (text, 1),
    )
    result = extract_financial_report(
        b"pdf",
        f"{symbol}_2026_1C.pdf",
    )
    metrics = to_financial_metrics(result.draft)
    validation = validate_financial_metrics(metrics)
    return result, metrics, validation


def test_standard_company_pdf_flow_preserves_monetary_values(monkeypatch):
    text = (
        "ÖRNEK SANAYİ ANONİM ŞİRKETİ\n"
        + COMMON_HEADER.format(symbol="SNYI")
        + """
Hasılat 1.200.000 1.000.000
Dönem net kârı 120.000 100.000
Toplam özkaynaklar 2.400.000 2.000.000
Finansal borçlar 600.000
Dönen varlıklar 1.500.000
Kısa vadeli yükümlülükler 750.000
İşletme faaliyetlerinden nakit akışı 180.000
Yatırım harcamaları 30.000
Toplam varlıklar 4.800.000 4.000.000
"""
    )

    result, metrics, validation = _extract(
        monkeypatch,
        text,
        "SNYI",
    )

    assert result.draft.company_profile == CompanyProfile.STANDARD
    assert result.draft.revenue == 1_200_000_000
    assert metrics.revenue_growth == 20
    assert metrics.net_margin == 10
    assert metrics.free_cash_flow == 150_000_000
    assert validation.completeness == 100
    assert validation.errors == []


def test_bank_pdf_flow_uses_bank_income_and_percentage_metrics(monkeypatch):
    text = (
        "ÖRNEK BANKASI ANONİM ŞİRKETİ\n"
        + COMMON_HEADER.format(symbol="TBNK")
        + """
Faiz gelirleri 2.000.000 1.600.000
Dönem net kârı 400.000 300.000
Toplam özkaynaklar 8.000.000 7.000.000
Toplam varlıklar 80.000.000 70.000.000
Sermaye yeterliliği oranı 18,50
Takipteki krediler oranı 2,10
Kredi/mevduat oranı 92,00
Net faiz marjı 6,20
Maliyet/gelir oranı 41,00
Doluluk oranı 88,00
"""
    )

    result, metrics, validation = _extract(
        monkeypatch,
        text,
        "TBNK",
    )

    assert result.draft.company_profile == CompanyProfile.BANK
    assert result.draft.revenue == 2_000_000_000
    assert metrics.capital_adequacy_ratio == 18.5
    assert metrics.npl_ratio == 2.1
    assert metrics.loan_to_deposit_ratio == 92
    assert metrics.net_interest_margin == 6.2
    assert metrics.cost_income_ratio == 41
    assert metrics.occupancy_rate is None
    assert validation.completeness == 100
    assert validation.errors == []


def test_insurance_pdf_flow_derives_premium_growth(monkeypatch):
    text = (
        "ÖRNEK SİGORTA ANONİM ŞİRKETİ\n"
        + COMMON_HEADER.format(symbol="TSGR")
        + """
Sigortacılık hizmet gelirleri 1.500.000 1.200.000
Brüt yazılan primler 2.400.000 2.000.000
Dönem net kârı 240.000 180.000
Toplam özkaynaklar 3.000.000 2.600.000
Dönen varlıklar 4.000.000
Kısa vadeli yükümlülükler 2.000.000
Toplam varlıklar 7.000.000 6.000.000
Bileşik oran 98,50
Ödeme gücü oranı 175,00
Takipteki krediler oranı 3,00
"""
    )

    result, metrics, validation = _extract(
        monkeypatch,
        text,
        "TSGR",
    )

    assert result.draft.company_profile == CompanyProfile.INSURANCE
    assert result.draft.premium_revenue == 2_400_000_000
    assert metrics.premium_growth == 20
    assert metrics.combined_ratio == 98.5
    assert metrics.solvency_ratio == 175
    assert metrics.npl_ratio is None
    assert validation.completeness == 100
    assert validation.errors == []


def test_reit_pdf_flow_keeps_nav_and_occupancy_as_percentages(monkeypatch):
    text = (
        "ÖRNEK GAYRİMENKUL YATIRIM ORTAKLIĞI ANONİM ŞİRKETİ\n"
        + COMMON_HEADER.format(symbol="TGY0")
        + """
Kira gelirleri 900.000 750.000
Dönem net kârı 300.000 250.000
Toplam özkaynaklar 5.000.000 4.500.000
Finansal borçlar 1.000.000
Dönen varlıklar 2.000.000
Kısa vadeli yükümlülükler 1.000.000
İşletme faaliyetlerinden nakit akışı 350.000
Toplam varlıklar 8.000.000 7.200.000
Net aktif değer iskontosu 24,50
Doluluk oranı 0,92
Sermaye yeterliliği oranı 18,00
"""
    )

    result, metrics, validation = _extract(
        monkeypatch,
        text,
        "TGY0",
    )

    assert result.draft.company_profile == CompanyProfile.REIT
    assert result.draft.revenue == 900_000_000
    assert metrics.nav_discount == 24.5
    assert metrics.occupancy_rate == 92
    assert metrics.capital_adequacy_ratio is None
    assert validation.completeness == 100
    assert validation.errors == []


@pytest.mark.parametrize(
    "symbol",
    ["SNYI", "TBNK", "TSGR", "TGY0"],
)
def test_sector_samples_use_verified_comparison_period(symbol, monkeypatch):
    text = (
        "ÖRNEK SANAYİ ANONİM ŞİRKETİ\n"
        + COMMON_HEADER.format(symbol=symbol)
        + "Hasılat 1.200.000 1.000.000"
    )

    result, _, _ = _extract(monkeypatch, text, symbol)

    assert result.draft.report_period_end == date(2026, 3, 31)
    assert result.comparison_period_end == date(2025, 3, 31)
    assert result.comparison_period_validated is True
