import csv
from io import StringIO

from app.data_quality.export import build_data_quality_csv
from app.data_quality.models import DataQualityRow
from app.sector.profiles import CompanyProfile
from app.validation.service import WarningConfirmationStatus


def test_data_quality_csv_preserves_turkish_text_and_warning_evidence():
    row = DataQualityRow(
        symbol="TBNK",
        company_name="Test Bankası A.Ş.",
        company_profile=CompanyProfile.BANK,
        completeness=87.5,
        status="Kontrol gerekli",
        missing_fields=["Net faiz marjı"],
        warnings=["Kredi / mevduat oranını kontrol edin."],
        warning_confirmation_status=WarningConfirmationStatus.REQUIRED,
        errors=[],
        calculation_check_status="Doğrulandı",
    )

    payload = build_data_quality_csv([row])
    text = payload.decode("utf-8-sig")
    records = list(csv.DictReader(StringIO(text)))

    assert len(records) == 1
    assert records[0]["Hisse"] == "TBNK"
    assert records[0]["Şirket"] == "Test Bankası A.Ş."
    assert records[0]["Sektör profili"] == "Banka"
    assert records[0]["Uyarı onayı"] == "Onay gerekli"
    assert records[0]["Eksik göstergeler"] == "Net faiz marjı"
    assert "Kredi / mevduat" in records[0]["Uyarılar"]
