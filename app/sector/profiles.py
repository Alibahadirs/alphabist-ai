from dataclasses import dataclass
from enum import Enum
import unicodedata


class CompanyProfile(str, Enum):
    STANDARD = "standard"
    BANK = "bank"
    INSURANCE = "insurance"
    REIT = "reit"
    FINANCIAL_SERVICES = "financial_services"


@dataclass(frozen=True)
class CompanyProfileResolution:
    profile: CompanyProfile
    financial_profile: CompanyProfile
    activity_profile: CompanyProfile | None
    has_conflict: bool = False


def reconcile_company_profiles(
    financial_profile: CompanyProfile,
    activity_profile: CompanyProfile | None = None,
) -> CompanyProfileResolution:
    financial = CompanyProfile(financial_profile)
    activity = (
        CompanyProfile(activity_profile)
        if activity_profile is not None
        else None
    )
    if activity is None or activity == financial:
        return CompanyProfileResolution(
            profile=financial,
            financial_profile=financial,
            activity_profile=activity,
        )
    if financial == CompanyProfile.STANDARD:
        return CompanyProfileResolution(
            profile=activity,
            financial_profile=financial,
            activity_profile=activity,
        )
    if activity == CompanyProfile.STANDARD:
        return CompanyProfileResolution(
            profile=financial,
            financial_profile=financial,
            activity_profile=activity,
        )
    return CompanyProfileResolution(
        profile=financial,
        financial_profile=financial,
        activity_profile=activity,
        has_conflict=True,
    )


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
