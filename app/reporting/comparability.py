from app.reporting.company_report import company_report_fingerprint
from app.reporting.models import (
    CompanyInvestmentReport,
    CompanyReportComparability,
)


def assess_company_report_comparability(
    first: CompanyInvestmentReport,
    second: CompanyInvestmentReport,
) -> CompanyReportComparability:
    for report in (first, second):
        if (
            not report.report_fingerprint
            or report.report_fingerprint
            != company_report_fingerprint(report)
        ):
            raise ValueError("Rapor içerik parmak izi doğrulanamadı.")
    if first.symbol.upper().strip() != second.symbol.upper().strip():
        raise ValueError("Yalnızca aynı şirkete ait raporlar karşılaştırılabilir.")

    previous, current = (
        (first, second)
        if first.generated_at <= second.generated_at
        else (second, first)
    )
    notes: list[str] = []
    financial_comparable = True
    if (
        previous.scoring_methodology_version
        != current.scoring_methodology_version
    ):
        financial_comparable = False
        notes.append("Temel analiz metodolojileri farklı.")
    if previous.company_profile != current.company_profile:
        financial_comparable = False
        notes.append("Şirket sektör profilleri farklı.")
    if (
        previous.report_period_end is None
        or current.report_period_end is None
    ):
        financial_comparable = False
        notes.append("Finansal dönem bilgisi eksik.")
    elif current.report_period_end < previous.report_period_end:
        financial_comparable = False
        notes.append("Finansal rapor dönemi geriye gidiyor.")

    technical_comparable = True
    if previous.technical_score is None or current.technical_score is None:
        technical_comparable = False
        notes.append("Karşılaştırılabilir iki teknik puan bulunmuyor.")
    if (
        previous.technical_methodology_version
        != current.technical_methodology_version
    ):
        technical_comparable = False
        notes.append("Teknik analiz metodolojileri farklı.")
    if (
        previous.technical_price_date is None
        or current.technical_price_date is None
    ):
        technical_comparable = False
        notes.append("Teknik fiyat tarihi eksik.")
    elif current.technical_price_date < previous.technical_price_date:
        technical_comparable = False
        notes.append("Teknik fiyat tarihi geriye gidiyor.")

    combined_comparable = bool(
        financial_comparable
        and technical_comparable
        and previous.combined_score is not None
        and current.combined_score is not None
    )
    if (
        financial_comparable
        and technical_comparable
        and not combined_comparable
    ):
        notes.append("Karşılaştırılabilir iki birleşik puan bulunmuyor.")

    return CompanyReportComparability(
        financial_comparable=financial_comparable,
        technical_comparable=technical_comparable,
        combined_comparable=combined_comparable,
        notes=list(dict.fromkeys(notes)),
    )
