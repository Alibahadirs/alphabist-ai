import re
import unicodedata
from difflib import SequenceMatcher


LEGAL_NAME_WORDS = {
    "a",
    "anonim",
    "as",
    "s",
    "sirket",
    "sirketi",
    "sanayi",
    "sanayii",
    "ticaret",
    "holding",
}
GENERIC_NAME_WORDS = {
    "banka",
    "bankasi",
    "enerji",
    "gayrimenkul",
    "ortakligi",
    "sigorta",
    "turk",
    "turkiye",
    "yatirim",
}


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    folded = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).casefold()
    return re.sub(r"[^a-z0-9 ]", " ", folded)


def _name_tokens(value: str) -> set[str]:
    return {
        token
        for token in _fold(value).split()
        if len(token) >= 2
        and token not in LEGAL_NAME_WORDS
        and token not in GENERIC_NAME_WORDS
    }


def _legal_name(value: str) -> str:
    return " ".join(
        token
        for token in _fold(value).split()
        if token not in LEGAL_NAME_WORDS
    )


def company_names_match(first: str, second: str) -> bool:
    if not first.strip() or not second.strip():
        return True
    if _legal_name(first) == _legal_name(second):
        return True
    first_tokens = _name_tokens(first)
    second_tokens = _name_tokens(second)
    if not first_tokens or not second_tokens:
        return False
    overlap = len(first_tokens & second_tokens) / min(
        len(first_tokens), len(second_tokens)
    )
    first_name = " ".join(sorted(first_tokens))
    second_name = " ".join(sorted(second_tokens))
    similarity = SequenceMatcher(None, first_name, second_name).ratio()
    return overlap >= 0.5 or similarity >= 0.6


def validate_report_identity(
    *,
    submitted_symbol: str,
    submitted_company_name: str,
    financial_symbol: str = "",
    financial_company_name: str = "",
    activity_symbol: str = "",
    activity_company_name: str = "",
) -> list[str]:
    errors: list[str] = []
    submitted = normalize_symbol(submitted_symbol)
    financial = normalize_symbol(financial_symbol)
    activity = normalize_symbol(activity_symbol)

    if financial and activity and financial != activity:
        errors.append(
            "Finansal rapor ile faaliyet raporunun hisse kodları farklı: "
            f"{financial} / {activity}."
        )
    report_symbols = {value for value in (financial, activity) if value}
    if submitted and report_symbols and submitted not in report_symbols:
        errors.append(
            f"Girilen hisse kodu ({submitted}), raporda bulunan "
            f"hisse koduyla ({' / '.join(sorted(report_symbols))}) uyuşmuyor."
        )

    if not company_names_match(financial_company_name, activity_company_name):
        errors.append(
            "Finansal rapor ile faaliyet raporunda farklı şirket unvanları bulundu."
        )
    for source_label, report_name in (
        ("finansal rapor", financial_company_name),
        ("faaliyet raporu", activity_company_name),
    ):
        if not company_names_match(submitted_company_name, report_name):
            errors.append(
                f"Girilen şirket unvanı {source_label} unvanıyla uyuşmuyor."
            )

    return list(dict.fromkeys(errors))
