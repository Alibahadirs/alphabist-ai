import csv
import io
from collections.abc import Sequence

from app.database.recovery_drill import RecoveryDrillRecord


def build_recovery_drill_csv(
    records: Sequence[RecoveryDrillRecord],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Kayıt ID",
            "Tatbikat zamanı",
            "Sonuç",
            "Kaynak dosya",
            "Kaynak SHA-256",
            "Şirket",
            "Toplam kayıt",
            "Açıklama",
            "Bütünlük",
            "Kayıt parmak izi",
        ]
    )
    for record in records:
        writer.writerow(
            [
                record.id,
                record.tested_at,
                "Başarılı" if record.success else "Başarısız",
                record.source_name,
                record.source_sha256,
                record.company_count,
                record.total_records,
                record.message,
                "Doğrulandı" if record.integrity_valid else "Geçersiz",
                record.fingerprint,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
