import csv
from collections.abc import Sequence
from io import StringIO

from app.data_quality.models import DataQualityRow, RemediationQueueRow
from app.sector.profiles import PROFILE_LABELS


def build_data_quality_csv(rows: Sequence[DataQualityRow]) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "Hisse",
            "Şirket",
            "Sektör profili",
            "Durum",
            "Yeterlilik (%)",
            "Uyarı onayı",
            "Eksik göstergeler",
            "Uyarılar",
            "Hatalar",
            "Hesap kontrolü",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "Hisse": row.symbol,
                "Şirket": row.company_name,
                "Sektör profili": PROFILE_LABELS[row.company_profile],
                "Durum": row.status,
                "Yeterlilik (%)": f"{row.completeness:.1f}",
                "Uyarı onayı": row.warning_confirmation_status.value,
                "Eksik göstergeler": " | ".join(row.missing_fields),
                "Uyarılar": " | ".join(row.warnings),
                "Hatalar": " | ".join(row.errors),
                "Hesap kontrolü": row.calculation_check_status,
            }
        )
    return output.getvalue().encode("utf-8-sig")


def build_remediation_queue_csv(
    rows: Sequence[RemediationQueueRow],
) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "Hisse",
            "Şirket",
            "Sektör profili",
            "Öncelik",
            "Öncelik puanı",
            "Görev türü",
            "Görev durumu",
            "Sorun kanıtı",
            "Sorun parmak izi",
            "Çalışma notu",
            "Son güncelleme",
            "Yapılacak işlem",
            "Karar engelleri",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "Hisse": row.symbol,
                "Şirket": row.company_name,
                "Sektör profili": PROFILE_LABELS[row.company_profile],
                "Öncelik": row.priority_level,
                "Öncelik puanı": row.priority_score,
                "Görev türü": row.task_category,
                "Görev durumu": row.workflow_status.value,
                "Sorun kanıtı": (
                    "Güncel"
                    if row.issue_fingerprint_matches
                    else "Değişti - yeniden aç"
                ),
                "Sorun parmak izi": row.issue_fingerprint,
                "Çalışma notu": row.workflow_note,
                "Son güncelleme": (
                    row.workflow_updated_at.isoformat()
                    if row.workflow_updated_at
                    else ""
                ),
                "Yapılacak işlem": row.recommended_action,
                "Karar engelleri": " | ".join(row.blockers),
            }
        )
    return output.getvalue().encode("utf-8-sig")
