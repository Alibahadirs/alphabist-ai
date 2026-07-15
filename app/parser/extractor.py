import re
import unicodedata
from io import BytesIO

from pypdf import PdfReader

from app.core.exceptions import PdfParsingError
from app.parser.models import (
    ActivityReportExtractionResult,
    CompanyMetadata,
    FinancialReportDraft,
    PdfExtractionResult,
)


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

SYMBOL_PATTERNS = (
    re.compile(r"(?:BIST|PAY KODU|HİSSE KODU)\s*[:\-]?\s*([A-Z0-9]{3,6})", re.I),
    re.compile(r"(?:BORSA KODU|İŞLEM KODU)\s*[:\-]?\s*([A-Z0-9]{3,6})", re.I),
)
IGNORED_FILENAME_WORDS = {
    "FAALIYET",
    "FINANSAL",
    "KONSOLIDE",
    "RAPOR",
    "REPORT",
    "SPK",
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


def _read_pdf(file_bytes: bytes) -> tuple[str, int]:
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
    return text, len(reader.pages)


def _symbol_from_filename(file_name: str) -> str:
    stem = file_name.rsplit(".", 1)[0].upper()
    candidates = re.findall(r"(?:^|[_\-\s])([A-Z0-9]{3,6})(?=[_\-\s]|$)", stem)
    for candidate in candidates:
        if candidate not in IGNORED_FILENAME_WORDS and not candidate.isdigit():
            return candidate
    return ""


def extract_company_metadata(text: str, file_name: str = "") -> CompanyMetadata:
    symbol = ""
    for pattern in SYMBOL_PATTERNS:
        match = pattern.search(text)
        if match:
            symbol = match.group(1).upper()
            break
    if not symbol and file_name:
        symbol = _symbol_from_filename(file_name)

    company_name = ""
    company_pattern = re.compile(
        r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9&.,()'\- ]{4,140}"
        r"(?:A\.?\s*Ş\.?|ANONİM ŞİRKETİ))",
        re.I,
    )
    for raw_line in text.splitlines()[:120]:
        line = " ".join(raw_line.split())
        match = company_pattern.search(line)
        if match:
            candidate = match.group(1).strip(" -:,\t")
            if "BAĞIMSIZ DENET" not in candidate.upper():
                company_name = candidate
                break

    period_months = None
    date_match = re.search(r"(?:30|31)[./-](0[369]|12)[./-]\d{4}", text)
    if date_match:
        period_months = int(date_match.group(1))

    return CompanyMetadata(
        symbol=symbol,
        company_name=company_name,
        period_months=period_months,
    )


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


def extract_financial_report(
    file_bytes: bytes,
    file_name: str = "",
) -> PdfExtractionResult:
    text, page_count = _read_pdf(file_bytes)
    draft, extracted_fields = extract_financial_values(text)
    metadata = extract_company_metadata(text, file_name)
    metadata_updates = {
        "symbol": metadata.symbol,
        "company_name": metadata.company_name,
    }
    if metadata.period_months is not None:
        metadata_updates["period_months"] = metadata.period_months
    draft = draft.model_copy(update=metadata_updates)
    warnings = []
    if len(extracted_fields) < 5:
        warnings.append(
            "Az sayıda kalem otomatik bulundu. Rakamları finansal tablodan kontrol edin."
        )

    return PdfExtractionResult(
        draft=draft,
        page_count=page_count,
        extracted_fields=extracted_fields,
        warnings=warnings,
    )


def extract_activity_report(
    file_bytes: bytes,
    file_name: str = "",
) -> ActivityReportExtractionResult:
    text, page_count = _read_pdf(file_bytes)
    metadata = extract_company_metadata(text, file_name)
    warnings = []
    if not metadata.symbol:
        warnings.append("Faaliyet raporunda hisse kodu bulunamadı.")
    if not metadata.company_name:
        warnings.append("Faaliyet raporunda şirket adı bulunamadı.")
    return ActivityReportExtractionResult(
        metadata=metadata,
        page_count=page_count,
        warnings=warnings,
    )
