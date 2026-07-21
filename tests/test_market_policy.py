from app.market_data.policy import get_source_policy, quote_source_is_eligible


def test_known_delayed_sources_have_explicit_policy():
    yahoo = get_source_policy("Yahoo Finance")
    fallback = get_source_policy("borsa-api / Yahoo Finance")

    assert yahoo.delayed is True
    assert yahoo.official is False
    assert yahoo.supports_daily_decisions is True
    assert fallback.supports_daily_decisions is True
    assert "yedek" in fallback.disclosure


def test_unknown_source_is_conservatively_excluded():
    policy = get_source_policy("Başka kaynak")

    assert policy.supports_daily_decisions is False
    assert "dahil edilmez" in policy.disclosure


def test_quote_eligibility_requires_matching_metadata():
    assert quote_source_is_eligible(
        {
            "source": "Yahoo Finance",
            "data_mode": "delayed",
            "official": False,
        }
    )
    assert not quote_source_is_eligible(
        {
            "source": "Yahoo Finance",
            "data_mode": "live",
            "official": False,
        }
    )
    assert not quote_source_is_eligible(
        {
            "source": "Bilinmeyen",
            "data_mode": "delayed",
            "official": False,
        }
    )
