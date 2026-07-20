from app.confidence.models import AnalysisConfidence
from app.data_quality.readiness import build_decision_readiness_summary
from app.scoring.models import FinancialMetrics
from app.technical.models import TechnicalQualityRow, TechnicalQualitySummary


def _company(symbol: str) -> FinancialMetrics:
    return FinancialMetrics(symbol=symbol, company_name=f"{symbol} A.Ş.")


def _confidence(ready: bool) -> AnalysisConfidence:
    return AnalysisConfidence(
        total=90 if ready else 60,
        status="Yüksek" if ready else "Düşük",
        decision="Al" if ready else "Doğrula / Karar verme",
        decision_ready=ready,
        completeness_component=50,
        source_component=20,
        report_component=10,
        period_component=5,
        validation_component=5,
        reasons=(
            ["Zorunlu göstergeler doğrulanabilir durumda."]
            if ready
            else ["Finansal rapor dönemi güncel değil."]
        ),
    )


def test_decision_readiness_combines_financial_and_technical_gates():
    technical = TechnicalQualitySummary(
        rows=[
            TechnicalQualityRow(
                symbol="READY",
                status="Güncel günlük veri",
                current=True,
            ),
            TechnicalQualityRow(
                symbol="FIN",
                status="Güncel günlük veri",
                current=True,
            ),
            TechnicalQualityRow(
                symbol="TECH",
                status="Eski fiyat",
                current=False,
            ),
            TechnicalQualityRow(
                symbol="BOTH",
                status="Kayıt yok",
                current=False,
            ),
        ],
        total=4,
        current_count=2,
        stale_count=1,
        missing_count=1,
        date_error_count=0,
    )
    summary = build_decision_readiness_summary(
        [_company("READY"), _company("FIN"), _company("TECH"), _company("BOTH")],
        {
            "READY": _confidence(True),
            "FIN": _confidence(False),
            "TECH": _confidence(True),
            "BOTH": _confidence(False),
        },
        technical,
    )

    rows = {row.symbol: row for row in summary.rows}
    assert summary.ready_count == 1
    assert summary.financial_only_count == 1
    assert summary.technical_only_count == 1
    assert summary.combined_issue_count == 1
    assert rows["READY"].status == "Karara hazır"
    assert rows["FIN"].status == "Finansal doğrulama gerekli"
    assert rows["TECH"].status == "Teknik yenileme gerekli"
    assert rows["BOTH"].status == "Finansal ve teknik doğrulama gerekli"
    assert rows["BOTH"].blockers == [
        "Finansal rapor dönemi güncel değil.",
        "Teknik kayıt: Kayıt yok",
    ]
    assert rows["BOTH"].priority_score == 85
    assert rows["BOTH"].priority_level == "Yüksek"
    assert rows["FIN"].priority_score == 55
    assert rows["TECH"].priority_score == 30
    assert rows["READY"].priority_score == 0
    assert rows["READY"].priority_level == "Hazır"


def test_decision_readiness_handles_missing_evaluations_safely():
    technical = TechnicalQualitySummary(
        rows=[],
        total=0,
        current_count=0,
        stale_count=0,
        missing_count=0,
        date_error_count=0,
    )
    summary = build_decision_readiness_summary(
        [_company("NONE")],
        {},
        technical,
    )

    assert summary.combined_issue_count == 1
    assert summary.rows[0].blockers == [
        "Finansal güven değerlendirmesi bulunmuyor.",
        "Teknik kayıt bulunmuyor.",
    ]
    assert summary.rows[0].priority_score == 100
    assert summary.rows[0].priority_level == "Acil"
