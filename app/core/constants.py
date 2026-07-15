CATEGORY_MAX_POINTS = {
    "profitability": 15,
    "growth": 15,
    "leverage": 15,
    "liquidity": 10,
    "cash_flow": 15,
    "efficiency": 10,
    "valuation": 10,
    "risk": 5,
    "management": 5,
}

GRADE_RULES = (
    (90, "A+", "Güçlü Al"),
    (80, "A", "Al"),
    (70, "B+", "İzle / Kademeli Al"),
    (60, "B", "İzle"),
    (50, "C", "Temkinli"),
    (0, "D", "Kaçın"),
)

TOTAL_SCORE = sum(CATEGORY_MAX_POINTS.values())