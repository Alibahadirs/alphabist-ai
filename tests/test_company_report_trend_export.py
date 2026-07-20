import csv
import io

from app.reporting.models import (
    CompanyReportComparability,
    CompanyReportTrendAlert,
    CompanyReportTrendSummary,
    ReportTrendAlertSeverity,
)
from app.reporting.trend_export import (
    serialize_company_report_trend_csv,
)


def test_company_report_trend_csv_contains_summary_and_alerts():
    trend = CompanyReportTrendSummary(
        symbol="TEST",
        report_count=2,
        latest_fingerprint="a" * 64,
        previous_fingerprint="b" * 64,
        trend_label="Zayıflıyor",
        comparability=CompanyReportComparability(
            financial_comparable=True,
            technical_comparable=True,
            combined_comparable=True,
        ),
        alpha_delta=-6,
        category_deltas={"profitability": -1.5},
        alerts=[
            CompanyReportTrendAlert(
                code="alpha_drop",
                severity=ReportTrendAlertSeverity.WARNING,
                message="Alpha Score belirgin düştü.",
            )
        ],
    )

    payload = serialize_company_report_trend_csv(trend)
    rows = list(
        csv.DictReader(
            io.StringIO(payload.decode("utf-8-sig"))
        )
    )

    assert payload.startswith(b"\xef\xbb\xbf")
    assert any(
        row["Kayıt türü"] == "Özet"
        and row["Alan"] == "Alpha Score değişimi"
        and row["Değer"] == "-6.0"
        for row in rows
    )
    assert any(
        row["Kayıt türü"] == "Kategori değişimi"
        and row["Alan"] == "profitability"
        for row in rows
    )
    assert any(
        row["Kayıt türü"] == "Uyarı"
        and row["Önem"] == "Uyarı"
        for row in rows
    )
