from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.sector.profiles import CompanyProfile


class ReportFieldKind(str, Enum):
    MONETARY = "monetary"
    PERCENTAGE = "percentage"
    SCORE = "score"


@dataclass(frozen=True)
class ReportFieldContract:
    kind: ReportFieldKind
    profiles: frozenset[CompanyProfile]


ALL_PROFILES = frozenset(CompanyProfile)

MONETARY_FIELDS = frozenset(
    {
        "revenue",
        "previous_revenue",
        "net_profit",
        "previous_net_profit",
        "equity",
        "previous_equity",
        "total_debt",
        "cash",
        "current_assets",
        "current_liabilities",
        "operating_cash_flow",
        "capital_expenditures",
        "total_assets",
        "previous_total_assets",
        "premium_revenue",
        "previous_premium_revenue",
    }
)

PROFILE_SECTOR_FIELDS = {
    CompanyProfile.STANDARD: frozenset(),
    CompanyProfile.BANK: frozenset(
        {
            "capital_adequacy_ratio",
            "npl_ratio",
            "loan_to_deposit_ratio",
            "net_interest_margin",
            "cost_income_ratio",
        }
    ),
    CompanyProfile.INSURANCE: frozenset(
        {
            "premium_revenue",
            "previous_premium_revenue",
            "premium_growth",
            "combined_ratio",
            "solvency_ratio",
        }
    ),
    CompanyProfile.REIT: frozenset(
        {
            "nav_discount",
            "occupancy_rate",
        }
    ),
    CompanyProfile.FINANCIAL_SERVICES: frozenset(
        {
            "capital_adequacy_ratio",
            "npl_ratio",
            "cost_income_ratio",
        }
    ),
}

PERCENTAGE_FIELDS = frozenset(
    {
        "capital_adequacy_ratio",
        "npl_ratio",
        "loan_to_deposit_ratio",
        "net_interest_margin",
        "cost_income_ratio",
        "premium_growth",
        "combined_ratio",
        "solvency_ratio",
        "nav_discount",
        "occupancy_rate",
    }
)

SCORE_FIELDS = frozenset(
    {
        "valuation_score_input",
        "management_score_input",
        "risk_score_input",
    }
)

FIELD_CONTRACTS = {
    **{
        field: ReportFieldContract(
            kind=ReportFieldKind.MONETARY,
            profiles=ALL_PROFILES,
        )
        for field in MONETARY_FIELDS
    },
    "premium_revenue": ReportFieldContract(
        kind=ReportFieldKind.MONETARY,
        profiles=frozenset({CompanyProfile.INSURANCE}),
    ),
    "previous_premium_revenue": ReportFieldContract(
        kind=ReportFieldKind.MONETARY,
        profiles=frozenset({CompanyProfile.INSURANCE}),
    ),
    **{
        field: ReportFieldContract(
            kind=ReportFieldKind.PERCENTAGE,
            profiles=frozenset(
                profile
                for profile, fields in PROFILE_SECTOR_FIELDS.items()
                if field in fields
            ),
        )
        for field in PERCENTAGE_FIELDS
    },
    **{
        field: ReportFieldContract(
            kind=ReportFieldKind.SCORE,
            profiles=ALL_PROFILES,
        )
        for field in SCORE_FIELDS
    },
}


def get_field_contract(field: str) -> ReportFieldContract:
    try:
        return FIELD_CONTRACTS[field]
    except KeyError as exc:
        raise KeyError(f"Tanımsız finansal rapor alanı: {field}") from exc


def is_field_allowed_for_profile(
    field: str,
    profile: CompanyProfile,
) -> bool:
    return CompanyProfile(profile) in get_field_contract(field).profiles


def sector_fields_for_profile(
    profile: CompanyProfile,
) -> frozenset[str]:
    return PROFILE_SECTOR_FIELDS[CompanyProfile(profile)]


def normalize_report_field_value(
    field: str,
    value: float,
    source_text: str = "",
) -> float:
    contract = get_field_contract(field)
    normalized = float(value)
    if contract.kind == ReportFieldKind.PERCENTAGE:
        context = source_text.casefold()
        if 0 < abs(normalized) <= 1 and (
            "%" in source_text or "oran" in context
        ):
            normalized *= 100
        if abs(normalized) > 1_000:
            raise ValueError(
                f"{field} yüzde alanına parasal tutar benzeri değer geldi."
            )
    elif contract.kind == ReportFieldKind.SCORE:
        if not 0 <= normalized <= 100:
            raise ValueError(f"{field} 0-100 aralığında olmalıdır.")
    return normalized
