import csv
import io
from collections.abc import Sequence

from app.database.restore_history import RestoreAuditRecord


def build_restore_audit_csv(
    records: Sequence[RestoreAuditRecord],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "Kayıt ID",
            "Tarih",
            "Durum",
            "Kaynak türü",
            "Dosya",
            "Kaynak SHA-256",
            "Gelen şirket",
            "Gelen toplam kayıt",
            "Güvenlik kopyası",
            "Açıklama",
            "Bütünlük",
            "Kayıt parmak izi",
        ]
    )
    for record in records:
        writer.writerow(
            [
                record.id,
                record.created_at,
                record.status,
                record.source_type,
                record.source_file_name,
                record.source_sha256,
                record.incoming_company_count,
                record.incoming_total_records,
                record.safety_backup_name,
                record.message,
                "Doğrulandı" if record.integrity_valid else "Geçersiz",
                record.fingerprint,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
