from enum import Enum
import unicodedata


class CompanyProfile(str, Enum):
    STANDARD = "standard"
    BANK = "bank"
    INSURANCE = "insurance"
    REIT = "reit"
    FINANCIAL_SERVICES = "financial_services"


PROFILE_LABELS = {
    CompanyProfile.STANDARD: "Standart şirket",
    CompanyProfile.BANK: "Banka",
    CompanyProfile.INSURANCE: "Sigorta / emeklilik",
    CompanyProfile.REIT: "Gayrimenkul yatırım ortaklığı",
    CompanyProfile.FINANCIAL_SERVICES: "Finansal hizmetler",
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold()


def detect_company_profile(company_name: str, report_text: str = "") -> CompanyProfile:
    source = company_name.strip() or report_text[:1500]
    haystack = _fold(source)
    if any(term in haystack for term in ("sigorta", "reasurans", "emeklilik")):
        return CompanyProfile.INSURANCE
    if any(term in haystack for term in ("gayrimenkul yat", " gyo")):
        return CompanyProfile.REIT
    if any(term in haystack for term in ("banka", "bank a.s")):
        return CompanyProfile.BANK
    if any(
        term in haystack
        for term in (
            "faktoring", "finansal kiralama", "menkul degerler",
            "yatirim menkul", "araci kurum",
        )
    ):
        return CompanyProfile.FINANCIAL_SERVICES
    return CompanyProfile.STANDARD
