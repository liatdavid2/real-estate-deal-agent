from __future__ import annotations

from typing import Any

from app.config import SearchProfile
from app.models import Listing


CITY_ALIASES: dict[str, list[str]] = {
    "גבעתיים": ["גבעתיים", "givatayim"],
    "givatayim": ["גבעתיים", "givatayim"],
    "חיפה": ["חיפה", "haifa"],
    "haifa": ["חיפה", "haifa"],
}


def _contains_any(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(str(keyword).lower() in text_lower for keyword in keywords if keyword)


def _contains_all(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return all(str(keyword).lower() in text_lower for keyword in keywords if keyword)


def _as_list(value: Any) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        return [str(v) for v in value]

    return [str(value)]


def _city_matches(text: str, configured_city: str) -> bool:
    city_key = configured_city.lower()
    aliases = CITY_ALIASES.get(city_key, [configured_city])

    return _contains_any(text, aliases)


def listing_matches_profile(listing: Listing, profile: SearchProfile) -> tuple[bool, list[str]]:
    filters = profile.filters
    failures: list[str] = []

    text = listing.searchable_text

    city = filters.get("city")
    if city and not _city_matches(text, str(city)):
        failures.append(f"city does not match {city}")

    min_rooms = filters.get("min_rooms")
    if min_rooms is not None:
        if listing.rooms is None:
            failures.append(f"rooms missing, expected at least {min_rooms}")
        elif listing.rooms < float(min_rooms):
            failures.append(f"rooms below {min_rooms}")

    max_rooms = filters.get("max_rooms")
    if max_rooms is not None:
        if listing.rooms is None:
            failures.append(f"rooms missing, expected at most {max_rooms}")
        elif listing.rooms > float(max_rooms):
            failures.append(f"rooms above {max_rooms}")

    max_price = filters.get("max_price")
    if max_price is not None:
        if listing.price is None:
            failures.append(f"price missing, expected at most {max_price}")
        elif listing.price > int(max_price):
            failures.append(f"price above {max_price}")

    min_price = filters.get("min_price")
    if min_price is not None:
        if listing.price is None:
            failures.append(f"price missing, expected at least {min_price}")
        elif listing.price < int(min_price):
            failures.append(f"price below {min_price}")

    # Important:
    # Missing size should not reject a listing.
    # Many Yad2/Madlan results do not expose size in the API result,
    # but they can still be relevant deals.
    min_size_sqm = filters.get("min_size_sqm")
    if min_size_sqm is not None and listing.size_sqm is not None:
        if listing.size_sqm < float(min_size_sqm):
            failures.append(f"size below {min_size_sqm}")

    max_size_sqm = filters.get("max_size_sqm")
    if max_size_sqm is not None and listing.size_sqm is not None:
        if listing.size_sqm > float(max_size_sqm):
            failures.append(f"size above {max_size_sqm}")

    min_floor = filters.get("min_floor")
    if min_floor is not None and listing.floor is not None:
        if listing.floor < int(min_floor):
            failures.append(f"floor below {min_floor}")

    max_floor = filters.get("max_floor")
    if max_floor is not None and listing.floor is not None:
        if listing.floor > int(max_floor):
            failures.append(f"floor above {max_floor}")

    neighborhoods = _as_list(filters.get("neighborhood_whitelist"))
    if neighborhoods and not _contains_any(text, neighborhoods):
        failures.append("neighborhood not in whitelist")

    required_keywords = _as_list(filters.get("required_keywords"))
    if required_keywords and not _contains_all(text, required_keywords):
        failures.append("missing required keywords")

    required_any_keywords = _as_list(filters.get("required_any_keywords"))
    if required_any_keywords and not _contains_any(text, required_any_keywords):
        failures.append("missing one of required_any_keywords")

    excluded_keywords = _as_list(filters.get("excluded_keywords"))
    if excluded_keywords and _contains_any(text, excluded_keywords):
        failures.append("contains excluded keyword")

    return len(failures) == 0, failures


def filter_listings(listings: list[Listing], profile: SearchProfile) -> list[Listing]:
    matched: list[Listing] = []
    seen_keys: set[str] = set()

    for listing in listings:
        if listing.stable_key in seen_keys:
            continue

        ok, _ = listing_matches_profile(listing, profile)

        if ok:
            matched.append(listing)
            seen_keys.add(listing.stable_key)

    return matched