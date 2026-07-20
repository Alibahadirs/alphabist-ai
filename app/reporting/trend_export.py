import csv
import io

from app.reporting.models import CompanyReportTrendSummary


def serialize_company_report_trend_csv(
    trend: CompanyReportTrendSummary,
) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = [
        "Kayıt türü",
        "Alan",
        "Değer",
        "Önem",
        "Açıklama",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    summary_fields = (
        ("Şirket", trend.symbol),
        ("Rapor sayısı", trend.report_count),
        ("Trend", trend.trend_label),
        ("Alpha Score değişimi", trend.alpha_delta),
        ("Analiz güveni değişimi", trend.confidence_delta),
        ("Teknik puan değişimi", trend.technical_delta),
        ("Birleşik puan değişimi", trend.combined_delta),
        ("Güncel içerik kimliği", trend.latest_fingerprint),
        ("Önceki içerik kimliği", trend.previous_fingerprint),
    )
    for label, value in summary_fields:
        writer.writerow(
            {
                "Kayıt türü": "Özet",
                "Alan": label,
                "Değer": "" if value is None else value,
                "Önem": "",
                "Açıklama": "",
            }
        )

    if trend.comparability is not None:
        for label, value in (
            (
                "Finansal karşılaştırılabilir",
                trend.comparability.financial_comparable,
            ),
            (
                "Teknik karşılaştırılabilir",
                trend.comparability.technical_comparable,
            ),
            (
                "Birleşik karşılaştırılabilir",
                trend.comparability.combined_comparable,
            ),
        ):
            writer.writerow(
                {
                    "Kayıt türü": "Karşılaştırılabilirlik",
                    "Alan": label,
                    "Değer": "Evet" if value else "Hayır",
                    "Önem": "",
                    "Açıklama": "",
                }
            )
        for note in trend.comparability.notes:
            writer.writerow(
                {
                    "Kayıt türü": "Karşılaştırılabilirlik",
                    "Alan": "Not",
                    "Değer": "",
                    "Önem": "Uyarı",
                    "Açıklama": note,
                }
            )

    for category, delta in trend.category_deltas.items():
        writer.writerow(
            {
                "Kayıt türü": "Kategori değişimi",
                "Alan": category,
                "Değer": delta,
                "Önem": "",
                "Açıklama": "",
            }
        )
    for alert in trend.alerts:
        writer.writerow(
            {
                "Kayıt türü": "Uyarı",
                "Alan": alert.code,
                "Değer": "",
                "Önem": alert.severity.value,
                "Açıklama": alert.message,
            }
        )

    return output.getvalue().encode("utf-8-sig")
