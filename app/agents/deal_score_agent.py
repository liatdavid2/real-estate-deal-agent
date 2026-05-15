from __future__ import annotations

from typing import Any

from app.config import SearchProfile
from app.models import Listing


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(k.lower() in text for k in keywords if k)


def score_listing(
    listing: Listing,
    profile: SearchProfile,
    status: str = "new",
    previous_price: int | None = None,
) -> tuple[int, list[str], list[str]]:
    scoring = profile.scoring
    filters = profile.filters
    reasons: list[str] = []
    risks: list[str] = []
    score = 40
    text = listing.searchable_text

    target_ppsqm = scoring.get("target_price_per_sqm")
    excellent_ppsqm = scoring.get("excellent_price_per_sqm")
    if listing.price_per_sqm is not None and target_ppsqm:
        if excellent_ppsqm and listing.price_per_sqm <= int(excellent_ppsqm):
            score += 25
            reasons.append(f"Excellent price per sqm: {listing.price_per_sqm:,} ILS/sqm")
        elif listing.price_per_sqm <= int(target_ppsqm):
            score += 18
            reasons.append(f"Price per sqm is below target: {listing.price_per_sqm:,} ILS/sqm")
        else:
            score -= 8
            risks.append(f"Price per sqm is above target: {listing.price_per_sqm:,} ILS/sqm")
    elif listing.price_per_sqm is None:
        risks.append("Missing price per sqm because price or size is unavailable")

    max_price = filters.get("max_price")
    if listing.price is not None and max_price:
        gap = int(max_price) - listing.price
        if gap > 0:
            pct = gap / int(max_price)
            add = min(15, int(pct * 40))
            score += add
            reasons.append(f"Asking price is {gap:,} ILS below configured max price")

    min_size = filters.get("min_size_sqm")
    if listing.size_sqm is not None and min_size and listing.size_sqm >= float(min_size):
        score += 5
        reasons.append(f"Size matches requirement: {listing.size_sqm:g} sqm")

    good_neighborhoods = _as_list(scoring.get("good_neighborhoods"))
    if good_neighborhoods and _contains_any(text, good_neighborhoods):
        score += 12
        reasons.append("Located in a preferred neighborhood")

    nice_keywords = _as_list(scoring.get("nice_to_have_keywords")) + _as_list(filters.get("nice_to_have_keywords"))
    matched_keywords = [k for k in nice_keywords if k.lower() in text]
    if matched_keywords:
        score += min(12, 3 * len(set(matched_keywords)))
        reasons.append("Positive listing signals: " + ", ".join(sorted(set(matched_keywords))))

    if status == "price_drop" and previous_price and listing.price:
        drop = previous_price - listing.price
        score += 15
        reasons.append(f"Price dropped by {drop:,} ILS since last seen")

    if listing.url is None:
        risks.append("Missing listing URL")
    if listing.price is None:
        risks.append("Missing price")
    if listing.size_sqm is None:
        risks.append("Missing size")
    if listing.rooms is None:
        risks.append("Missing room count")
    if not any(k.lower() in text for k in ["מעלית", "חניה", "ממד", "ממ\"ד"]):
        risks.append("Elevator, parking, or safe room not clearly mentioned")

    return max(0, min(100, score)), reasons, risks
