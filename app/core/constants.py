from enum import Enum


class DecisionLabel(str, Enum):
    STRONG_BUY = "Güçlü Al"
    BUY = "Al"
    WATCH = "İzle"
    HOLD = "Bekle"
    AVOID = "Kaçın"


class RiskLevel(str, Enum):
    LOW = "Düşük"
    MEDIUM = "Orta"
    HIGH = "Yüksek"


ALPHA_SCORE_MIN = 0
ALPHA_SCORE_MAX = 100

GRADE_THRESHOLDS = {
    "A+": 95,
    "A": 90,
    "A-": 85,
    "B+": 80,
    "B": 70,
    "C+": 60,
    "C": 50,
    "D": 0,
}

DECISION_THRESHOLDS = {
    DecisionLabel.STRONG_BUY: 90,
    DecisionLabel.BUY: 80,
    DecisionLabel.WATCH: 70,
    DecisionLabel.HOLD: 60,
    DecisionLabel.AVOID: 0,
}

DEFAULT_SCORE_WEIGHTS = {
    "profitability": 15,
    "growth": 15,
    "debt": 15,
    "liquidity": 10,
    "cash_flow": 15,
    "efficiency": 10,
    "valuation": 10,
    "risk": 5,
    "management": 5,
}