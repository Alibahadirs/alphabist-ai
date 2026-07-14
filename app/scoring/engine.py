from app.scoring.models import FinancialMetrics, ScoreBreakdown

def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))

def scale(value, low, high, points):
    return round(clamp((value-low)/(high-low), 0, 1) * points, 2)

def calculate_alpha_score(m: FinancialMetrics) -> ScoreBreakdown:
    profitability = scale(m.net_margin, 0, 25, 7.5) + scale(m.roe, 0, 35, 7.5)
    growth = scale(m.revenue_growth, -10, 40, 7.5) + scale(m.net_profit_growth, -20, 60, 7.5)
    leverage = round(clamp((2-m.debt_to_equity)/2, 0, 1) * 15, 2)
    liquidity = scale(m.current_ratio, 0.5, 2.5, 10)
    cash_flow = (7.5 if m.operating_cash_flow > 0 else 0) + (7.5 if m.free_cash_flow > 0 else 0)
    efficiency = scale(m.asset_turnover, 0, 1.5, 10)
    valuation = round(clamp(m.valuation_score_input, 0, 100) / 10, 2)
    risk = round(clamp(m.risk_score_input, 0, 100) / 20, 2)
    management = round(clamp(m.management_score_input, 0, 100) / 20, 2)
    total = round(sum([profitability, growth, leverage, liquidity, cash_flow, efficiency, valuation, risk, management]), 2)
    if total >= 90: grade, decision = 'A+', 'Güçlü Al'
    elif total >= 80: grade, decision = 'A', 'Al'
    elif total >= 70: grade, decision = 'B+', 'İzle / Kademeli Al'
    elif total >= 60: grade, decision = 'B', 'İzle'
    elif total >= 50: grade, decision = 'C', 'Temkinli'
    else: grade, decision = 'D', 'Kaçın'
    return ScoreBreakdown(profitability=profitability, growth=growth, leverage=leverage, liquidity=liquidity, cash_flow=cash_flow, efficiency=efficiency, valuation=valuation, risk=risk, management=management, total=total, grade=grade, decision=decision)
