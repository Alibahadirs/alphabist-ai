import csv
import io

from app.reporting.models import CompanyReportTrendMonitor
from app.sector.profiles import PROFILE_LABELS


def serialize_company_report_trend_monitor_csv(
    monitor: CompanyReportTrendMonitor,
) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = [
        "Hisse",
        "Şirket",
        "Sektör profili",
        "Rapor sayısı",
        "Son rapor zamanı",
        "Finansal dönem",
        "Alpha Score",
        "Alpha değişimi",
        "Birleşik değişim",
        "Trend",
        "Karara hazır",
        "Önem",
        "Uyarı sayısı",
        "Öncelik puanı",
        "Öncelikli uyarı",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in monitor.rows:
        writer.writerow(
            {
                "Hisse": row.symbol,
                "Şirket": row.company_name,
                "Sektör profili": PROFILE_LABELS[row.company_profile],
                "Rapor sayısı": row.report_count,
                "Son rapor zamanı": row.latest_generated_at.isoformat(),
                "Finansal dönem": (
                    row.latest_report_period_end.isoformat()
                    if row.latest_report_period_end
                    else ""
                ),
                "Alpha Score": row.latest_alpha_score,
                "Alpha değişimi": (
                    "" if row.alpha_delta is None else row.alpha_delta
                ),
                "Birleşik değişim": (
                    "" if row.combined_delta is None else row.combined_delta
                ),
                "Trend": row.trend_label,
                "Karara hazır": "Evet" if row.decision_ready else "Hayır",
                "Önem": row.alert_severity.value,
                "Uyarı sayısı": row.alert_count,
                "Öncelik puanı": row.priority_score,
                "Öncelikli uyarı": row.primary_alert,
            }
        )
    return output.getvalue().encode("utf-8-sig")
