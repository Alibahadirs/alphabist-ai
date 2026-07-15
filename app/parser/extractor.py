import re
import unicodedata
from io import BytesIO

from pypdf import PdfReader

from app.core.exceptions import PdfParsingError
from app.parser.models import FinancialReportDraft, PdfExtractionResult


NUMBER_PATTERN = re.compile(
    r"\(?-?\d{1,3}(?:\.\d{3})+(?:,\d+)?\)?"
    r"|\(?-?\d+(?:[.,]\d+)?\)?"
)

FIELD_LABELS = {
    ("revenue", "previous_revenue"): (
        "hasılat",
        "satış gelirleri",
        "satışlar",
    ),
    ("net_profit", "previous_net_profit"): (
        "ana ortaklık payları",
        "dönem net kârı",
        "dönem net karı",
        "dönem kârı",
        "dönem karı",
    ),
    ("cash",): (
        "nakit ve nakit benzerleri",
        "nakit ve nakit benzeri",
    ),
    ("current_assets",): ("dönen varlıklar",),
    ("current_liabilities",): (
        "kısa vadeli yükümlülükler",
        "kısa vadeli borçlar",
    ),
    ("equity",): (
        "toplam özkaynaklar",
        "özkaynaklar",
    ),
    ("total_assets",): (
        "toplam varlıklar",
        "toplam aktifler",
    ),
    ("total_debt",): (
        "finansal borçlar",
        "toplam borçlanmalar",
        "borçlanmalar",
    ),
    ("operating_cash_flow",): (
        "işletme faaliyetlerinden nakit akışları",
        "işletme faaliyetlerinden nakit akışı",
        "faaliyetlerden elde edilen nakit akışları",
    ),
    ("capital_expenditures",): (
        "maddi ve maddi olmayan duran varlık alımları",
        "maddi duran varlık alımları",
        "yatırım harcamaları",
    ),
}


def parse_turkish_number(raw_value: str) -> float:
    value = raw_value.strip()
    negative = value.startswith("-") or (
        value.startswith("(") and value.endswith(")")
    )
    value = re.sub(r"[^0-9,.]", "", value)
    if not value:
        raise ValueError("Sayısal değer bulunamadı.")

    if "," in value:
        normalized = value.replace(".", "").replace(",", ".")
    else:
        parts = value.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            normalized = "".join(parts)
        else:
            normalized = value

    number = float(normalized)
    return -number if negative else number


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def _line_values(line: str) -> list[float]:
    values = [parse_turkish_number(item) for item in NUMBER_PATTERN.findall(line)]

    if len(values) >= 3 and abs(values[0]) < 1_000:
        values = values[1:]
    return values


def extract_financial_values(
    text: str,
) -> tuple[FinancialReportDraft, list[str]]:
    extracted: dict[str, float] = {}

    for line in text.splitlines():
        clean_line = " ".join(line.split())
        if not clean_line:
            continue

        folded_line = _fold(clean_line)
        for fields, labels in FIELD_LABELS.items():
            if any(field in extracted for field in fields):
                continue

            for label in labels:
                if _fold(label) not in folded_line:
                    continue

                values = _line_values(clean_line)
                if not values:
                    continue

                extracted[fields[0]] = values[0]
                if len(fields) > 1 and len(values) > 1:
                    extracted[fields[1]] = values[1]
                break

    return FinancialReportDraft(**extracted), sorted(extracted)


def extract_financial_report(file_bytes: bytes) -> PdfExtractionResult:
    if not file_bytes:
        raise PdfParsingError("PDF dosyası boş.")

    try:
        reader = PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise PdfParsingError(f"PDF okunamadı: {exc}") from exc

    text = "\n".join(pages).strip()
    if not text:
        raise PdfParsingError(
            "PDF içinde okunabilir metin bulunamadı. Dosya taranmış görüntü olabilir."
        )

    draft, extracted_fields = extract_financial_values(text)
    warnings = []
    if len(extracted_fields) < 5:
        warnings.append(
            "Az sayıda kalem otomatik bulundu. Rakamları finansal tablodan kontrol edin."
        )

    return PdfExtractionResult(
        draft=draft,
        page_count=len(reader.pages),
        extracted_fields=extracted_fields,
        warnings=warnings,
    )
