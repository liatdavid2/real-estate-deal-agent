from app.agents.deal_score_agent import score_listing
from app.agents.filter_agent import listing_matches_profile
from app.config import SearchProfile, SourceConfig
from app.models import Listing


def _profile():
    return SearchProfile(
        name="haifa_test",
        transaction="sale",
        filters={
            "city": "חיפה",
            "min_rooms": 3,
            "max_rooms": 3,
            "max_price": 1450000,
            "min_size_sqm": 55,
            "neighborhood_whitelist": ["אחוזה", "כרמליה"],
            "required_any_keywords": ["מושכרת", "שוכר"],
        },
        scoring={
            "target_price_per_sqm": 22000,
            "excellent_price_per_sqm": 19000,
            "good_neighborhoods": ["אחוזה", "כרמליה"],
            "nice_to_have_keywords": ["מושכרת", "חניה"],
        },
        sources=[SourceConfig(name="test", actor_id="test/actor")],
    )


def test_listing_matches_investment_profile():
    listing = Listing(
        source="test",
        listing_id="1",
        title="דירת 3 חדרים מושכרת באחוזה",
        city="חיפה",
        neighborhood="אחוזה",
        price=1200000,
        rooms=3,
        size_sqm=65,
        description="דירה מושכרת עם שוכר טוב",
    )
    ok, failures = listing_matches_profile(listing, _profile())
    assert ok, failures


def test_deal_score_rewards_low_price_per_sqm():
    listing = Listing(
        source="test",
        listing_id="1",
        title="דירת 3 חדרים מושכרת באחוזה עם חניה",
        city="חיפה",
        neighborhood="אחוזה",
        price=1200000,
        rooms=3,
        size_sqm=70,
        description="מושכרת עם חניה",
    )
    score, reasons, risks = score_listing(listing, _profile())
    assert score >= 75
    assert reasons
