from app.sector.profiles import CompanyProfile


BASE_CATEGORY_LABELS = {
    "profitability": "Karlılık",
    "growth": "Büyüme",
    "leverage": "Borçluluk",
    "liquidity": "Likidite",
    "cash_flow": "Nakit akışı",
    "efficiency": "Verimlilik",
    "valuation": "Değerleme",
    "risk": "Risk dayanıklılığı",
    "management": "Yönetim",
}

PROFILE_CATEGORY_LABEL_OVERRIDES = {
    CompanyProfile.BANK: {
        "leverage": "Sermaye yeterliliği",
        "liquidity": "Fonlama / likidite",
        "cash_flow": "Aktif kalitesi",
        "efficiency": "Maliyet verimliliği",
    },
    CompanyProfile.INSURANCE: {
        "leverage": "Ödeme gücü",
        "cash_flow": "Teknik denge",
        "efficiency": "Teknik verimlilik",
    },
    CompanyProfile.REIT: {
        "cash_flow": "Nakit akışı / doluluk",
        "efficiency": "Portföy verimliliği",
    },
    CompanyProfile.FINANCIAL_SERVICES: {
        "leverage": "Sermaye / borçluluk",
        "cash_flow": "Aktif kalitesi",
        "efficiency": "Maliyet verimliliği",
    },
}

PROFILE_CATEGORY_EVIDENCE = {
    CompanyProfile.STANDARD: {
        "profitability": "Net kâr marjı ve ROE",
        "growth": "Ciro ve net kâr büyümesi",
        "leverage": "Borç / özkaynak",
        "liquidity": "Cari oran",
        "cash_flow": "Operasyonel ve serbest nakit akışı",
        "efficiency": "Aktif devir hızı",
    },
    CompanyProfile.BANK: {
        "profitability": "ROE ve net faiz marjı",
        "growth": "Bankacılık geliri ve net kâr büyümesi",
        "leverage": "Sermaye yeterliliği oranı",
        "liquidity": "Kredi / mevduat oranı",
        "cash_flow": "Takipteki kredi oranı",
        "efficiency": "Maliyet / gelir oranı",
    },
    CompanyProfile.INSURANCE: {
        "profitability": "ROE ve net kâr marjı",
        "growth": "Prim ve net kâr büyümesi",
        "leverage": "Ödeme gücü / sermaye yeterliliği",
        "liquidity": "Cari oran",
        "cash_flow": "Bileşik oran",
        "efficiency": "Bileşik oran",
    },
    CompanyProfile.REIT: {
        "profitability": "Net kâr marjı ve ROE",
        "growth": "Gelir ve net kâr büyümesi",
        "leverage": "Borç / özkaynak",
        "liquidity": "Cari oran",
        "cash_flow": "Operasyonel nakit akışı ve doluluk",
        "efficiency": "Doluluk oranı",
    },
    CompanyProfile.FINANCIAL_SERVICES: {
        "profitability": "Net kâr marjı ve ROE",
        "growth": "Faaliyet geliri ve net kâr büyümesi",
        "leverage": "Sermaye yeterliliği veya borç / özkaynak",
        "liquidity": "Cari oran",
        "cash_flow": "Takipteki alacak oranı",
        "efficiency": "Maliyet / gelir oranı",
    },
}

COMMON_CATEGORY_EVIDENCE = {
    "valuation": "Değerleme girdisi",
    "risk": "Risk dayanıklılığı girdisi",
    "management": "Yönetim ve sermaye disiplini girdisi",
}


def get_category_label(
    profile: CompanyProfile,
    category: str,
) -> str:
    effective_profile = CompanyProfile(profile)
    return PROFILE_CATEGORY_LABEL_OVERRIDES.get(
        effective_profile,
        {},
    ).get(category, BASE_CATEGORY_LABELS[category])


def get_category_evidence(
    profile: CompanyProfile,
    category: str,
) -> str:
    effective_profile = CompanyProfile(profile)
    profile_evidence = PROFILE_CATEGORY_EVIDENCE[effective_profile]
    if category in profile_evidence:
        return profile_evidence[category]
    return COMMON_CATEGORY_EVIDENCE[category]
