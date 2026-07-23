import pytest

from app.parser.contracts import (
    MONETARY_FIELDS,
    PERCENTAGE_FIELDS,
    ReportFieldKind,
    get_field_contract,
    is_field_allowed_for_profile,
    sector_fields_for_profile,
)
from app.sector.profiles import CompanyProfile


def test_monetary_and_percentage_fields_have_distinct_contracts():
    assert get_field_contract("revenue").kind == ReportFieldKind.MONETARY
    assert (
        get_field_contract("capital_adequacy_ratio").kind
        == ReportFieldKind.PERCENTAGE
    )
    assert MONETARY_FIELDS.isdisjoint(PERCENTAGE_FIELDS)


@pytest.mark.parametrize(
    ("profile", "allowed", "blocked"),
    [
        (
            CompanyProfile.BANK,
            "capital_adequacy_ratio",
            "occupancy_rate",
        ),
        (
            CompanyProfile.INSURANCE,
            "combined_ratio",
            "npl_ratio",
        ),
        (
            CompanyProfile.REIT,
            "nav_discount",
            "solvency_ratio",
        ),
        (
            CompanyProfile.FINANCIAL_SERVICES,
            "cost_income_ratio",
            "occupancy_rate",
        ),
    ],
)
def test_sector_fields_are_restricted_by_company_profile(
    profile,
    allowed,
    blocked,
):
    assert is_field_allowed_for_profile(allowed, profile) is True
    assert is_field_allowed_for_profile(blocked, profile) is False
    assert allowed in sector_fields_for_profile(profile)


def test_insurance_premium_amount_is_not_scaled_for_other_profiles():
    assert (
        is_field_allowed_for_profile(
            "premium_revenue",
            CompanyProfile.INSURANCE,
        )
        is True
    )
    assert (
        is_field_allowed_for_profile(
            "premium_revenue",
            CompanyProfile.BANK,
        )
        is False
    )


def test_unknown_field_contract_fails_closed():
    with pytest.raises(KeyError, match="Tanımsız"):
        get_field_contract("mystery_metric")
