import pytest

from app.core.exceptions import ValidationError
from app.parser.converter import to_financial_metrics
from app.parser.extractor import (
    extract_company_metadata,
    extract_financial_values,
    parse_turkish_number,
)
from app.sector.profiles import CompanyProfile
from app.parser.models import FinancialReportDraft


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("22.393.593.959", 22_393_593_959),
        ("1.250,50", 1_250.50),
        ("(812.000.000)", -812_000_000),
        ("-42,5", -42.5),
    ],
)
def test_parse_turkish_number(raw_value, expected):
    assert parse_turkish_number(raw_value) == expected


def test_bank_profile_is_detected_from_report_title():
    metadata = extract_company_metadata(
        "ÖRNEK BANKASI ANONİM ŞİRKETİ 31.03.2026 FAALİYET RAPORU"
    )

    assert metadata.company_profile == CompanyProfile.BANK


def test_extract_financial_values_from_statement_text():
    text = """
    Hasılat 22.393.593.959 18.161.075.758
    Dönem kârı 3.070.000.000 812.000.000
    Nakit ve nakit benzerleri 12.970.000.000 8.200.000.000
    Dönen varlıklar 44.700.000.000 39.000.000.000
    Kısa vadeli yükümlülükler 27.500.000.000 25.000.000.000
    Toplam özkaynaklar 42.100.000.000 38.000.000.000
    Toplam varlıklar 71.700.000.000 65.000.000.000
    İşletme faaliyetlerinden nakit akışı 3.040.000.000 900.000.000
    """

    draft, fields = extract_financial_values(text)

    assert draft.revenue == 22_393_593_959
    assert draft.previous_revenue == 18_161_075_758
    assert draft.net_profit == 3_070_000_000
    assert draft.equity == 42_100_000_000
    assert "operating_cash_flow" in fields


def test_note_numbers_and_empty_current_period_are_not_financial_values():
    text = """
    Konsolide Özkaynaklar Değişim Tabloları 4
    Dönem Karı Vergi Yükümlülüğü -- --
    Özkaynaklar 3.901.690.386 2.304.982.463
    Net Dönem Karı 1.426.444.983 (51.183.071)
    Hasılat 12 -- 709.628
    """

    draft, _ = extract_financial_values(text)

    assert draft.revenue == 0
    assert draft.previous_revenue == 709_628
    assert draft.net_profit == 1_426_444_983
    assert draft.previous_net_profit == -51_183_071
    assert draft.equity == 3_901_690_386


def test_convert_quarterly_report_to_scoring_metrics():
    draft = FinancialReportDraft(
        symbol="TEST",
        company_name="Test Şirketi",
        period_months=3,
        revenue=120,
        previous_revenue=100,
        net_profit=12,
        previous_net_profit=10,
        equity=240,
        total_debt=120,
        current_assets=200,
        current_liabilities=100,
        operating_cash_flow=20,
        capital_expenditures=5,
        total_assets=480,
    )

    metrics = to_financial_metrics(draft)

    assert metrics.revenue_growth == pytest.approx(20)
    assert metrics.net_margin == pytest.approx(10)
    assert metrics.roe == pytest.approx(20)
    assert metrics.current_ratio == pytest.approx(2)
    assert metrics.free_cash_flow == pytest.approx(15)
    assert metrics.asset_turnover == pytest.approx(1)


def test_loss_to_profit_turnaround_is_not_shown_as_growth_percentage():
    draft = FinancialReportDraft(
        symbol="TEST",
        company_name="Test Şirketi",
        revenue=0,
        previous_revenue=709_628,
        net_profit=1_426_444_983,
        previous_net_profit=-51_183_071,
        equity=3_901_690_386,
        period_months=3,
    )

    metrics = to_financial_metrics(draft)

    assert metrics.revenue_growth == -100
    assert metrics.net_margin == 0
    assert metrics.net_profit_growth == 0
    assert metrics.roe == pytest.approx(146.24, rel=0.01)


def test_converter_requires_symbol_and_company_name():
    with pytest.raises(ValidationError):
        to_financial_metrics(FinancialReportDraft())


def test_extract_company_metadata_from_activity_report_text():
    text = """
    AKSA AKRİLİK KİMYA SANAYİİ A.Ş.
    BIST: AKSA
    01.01.2026 - 30.06.2026 FAALİYET RAPORU
    """

    metadata = extract_company_metadata(text)

    assert metadata.symbol == "AKSA"
    assert metadata.company_name == "AKSA AKRİLİK KİMYA SANAYİİ A.Ş."
    assert metadata.period_months == 6


def test_extract_symbol_from_pdf_filename_when_text_has_no_code():
    metadata = extract_company_metadata(
        "GÜBRE FABRİKALARI TÜRK A.Ş. FAALİYET RAPORU",
        "GUBRF_2026_1C.pdf",
    )

    assert metadata.symbol == "GUBRF"
    assert metadata.company_name == "GÜBRE FABRİKALARI TÜRK A.Ş."


def test_normalizes_kervansaray_report_filename_to_official_symbol():
    metadata = extract_company_metadata(
        "KERVANSARAY YATIRIM HOLDİNG ANONİM ŞİRKETİ",
        "1-KRVN Özet 03.2026 Rapor F.pdf",
    )

    assert metadata.symbol == "KERVN"


def test_infers_kervansaray_symbol_from_company_name():
    metadata = extract_company_metadata(
        "KERVANSARAY YATIRIM HOLDİNG ANONİM ŞİRKETİ"
    )

    assert metadata.symbol == "KERVN"
