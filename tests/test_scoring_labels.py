import pytest

from app.scoring.labels import get_category_evidence, get_category_label
from app.sector.profiles import CompanyProfile


@pytest.mark.parametrize(
    ("profile", "category", "expected"),
    [
        (CompanyProfile.STANDARD, "cash_flow", "Nakit akışı"),
        (CompanyProfile.BANK, "cash_flow", "Aktif kalitesi"),
        (CompanyProfile.BANK, "leverage", "Sermaye yeterliliği"),
        (CompanyProfile.INSURANCE, "cash_flow", "Teknik denge"),
        (CompanyProfile.REIT, "efficiency", "Portföy verimliliği"),
        (
            CompanyProfile.FINANCIAL_SERVICES,
            "leverage",
            "Sermaye / borçluluk",
        ),
    ],
)
def test_category_label_matches_sector_methodology(
    profile,
    category,
    expected,
):
    assert get_category_label(profile, category) == expected


def test_bank_asset_quality_discloses_npl_evidence():
    assert (
        get_category_evidence(CompanyProfile.BANK, "cash_flow")
        == "Takipteki kredi oranı"
    )


def test_common_manual_categories_keep_their_evidence():
    assert (
        get_category_evidence(CompanyProfile.REIT, "valuation")
        == "Değerleme girdisi"
    )
