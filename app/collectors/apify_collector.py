from __future__ import annotations

import os
import re
from typing import Any, Iterable

from apify_client import ApifyClient

from app.budget.apify_budget import ApifyBudgetGuard
from app.config import SearchProfile, SourceConfig
from app.models import Listing


class ApifyCollectionError(RuntimeError):
    pass


_NUMBER_PATTERN = re.compile(r"[-+]?\d[\d,\.]*")


def _first(raw: dict[str, Any], keys: Iterable[str]) -> Any:
    lower_map = {str(k).lower(): v for k, v in raw.items()}
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
        lower_key = key.lower()
        if lower_key in lower_map and lower_map[lower_key] not in (None, ""):
            return lower_map[lower_key]
    return None


def _nested_first(raw: dict[str, Any], paths: Iterable[str]) -> Any:
    for path in paths:
        cur: Any = raw
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    text = str(value)
    match = _NUMBER_PATTERN.search(text.replace("₪", ""))
    if not match:
        return None
    cleaned = match.group(0).replace(",", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", ".")
    match = _NUMBER_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v not in (None, "")]
    if isinstance(value, dict):
        return [str(k) for k, v in value.items() if v]
    return [str(value)] if str(value).strip() else []


def _detect_transaction(raw: dict[str, Any], default_transaction: str) -> str:
    raw_value = _first(raw, ["transaction", "dealType", "type", "category", "listingType"])
    text = f"{raw_value or ''} {raw}".lower()
    if any(token in text for token in ["rent", "השכר", "שכירות", "להשכרה"]):
        return "rent"
    if any(token in text for token in ["sale", "sell", "מכיר", "למכירה"]):
        return "sale"
    return default_transaction if default_transaction in {"sale", "rent"} else "unknown"


def normalize_apify_item(raw: dict[str, Any], source_name: str, default_transaction: str) -> Listing:
    listing_id = _first(raw, [
        "id", "listingId", "listing_id", "adId", "ad_id", "assetId", "asset_id",
        "propertyId", "property_id", "token",
    ])
    url = _first(raw, ["url", "link", "listingUrl", "listing_url", "pageUrl", "page_url"])
    if not listing_id:
        listing_id = url or str(abs(hash(str(raw))))

    title = _first(raw, ["title", "heading", "name", "subtitle", "propertyTitle"]) or ""
    city = _first(raw, ["city", "cityName", "city_name", "settlement"])
    neighborhood = _first(raw, ["neighborhood", "neighborhoodName", "neighborhood_name", "area", "region"])
    street = _first(raw, ["street", "streetName", "street_name"])
    address = _first(raw, ["address", "fullAddress", "full_address", "location"])
    description = _first(raw, ["description", "desc", "text", "details", "body"]) or ""

    price = _to_int(_first(raw, ["price", "priceValue", "price_value", "amount", "askingPrice"]))
    rooms = _to_float(_first(raw, ["rooms", "roomCount", "room_count", "numberOfRooms", "rooms_count"]))
    size_sqm = _to_float(_first(raw, ["area", "size", "sqm", "squareMeters", "square_meters", "builtArea", "meter"] ))
    floor = _to_int(_first(raw, ["floor", "floorNumber", "floor_number"] ))
    total_floors = _to_int(_first(raw, ["totalFloors", "total_floors", "floorsInBuilding", "floors_in_building"] ))

    amenities = []
    for candidate in [
        _first(raw, ["amenities", "features", "tags", "properties", "extras"]),
        _nested_first(raw, ["metadata.amenities", "metadata.features", "property.amenities"]),
    ]:
        amenities.extend(_to_list(candidate))

    images = _to_list(_first(raw, ["images", "photos", "imageUrls", "image_urls", "pictures"] ))
    contact_name = _first(raw, ["contactName", "contact_name", "agentName", "agent_name", "sellerName"])
    contact_phone = _first(raw, ["phone", "contactPhone", "contact_phone", "agentPhone"])

    return Listing(
        source=source_name,
        listing_id=str(listing_id),
        title=str(title),
        city=str(city) if city is not None else None,
        neighborhood=str(neighborhood) if neighborhood is not None else None,
        street=str(street) if street is not None else None,
        address=str(address) if address is not None else None,
        price=price,
        rooms=rooms,
        size_sqm=size_sqm,
        floor=floor,
        total_floors=total_floors,
        transaction=_detect_transaction(raw, default_transaction),
        url=str(url) if url is not None else None,
        description=str(description),
        amenities=amenities,
        images=images,
        contact_name=str(contact_name) if contact_name is not None else None,
        contact_phone=str(contact_phone) if contact_phone is not None else None,
        raw=raw,
    )


class ApifyRealEstateCollector:
    def __init__(self, token: str | None = None, wait_secs: int | None = None, budget_guard: ApifyBudgetGuard | None = None):
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise ApifyCollectionError("APIFY_TOKEN is required for real API collection.")
        self.client = ApifyClient(self.token)
        self.wait_secs = wait_secs or int(os.getenv("APIFY_WAIT_SECS", "120"))
        self.budget_guard = budget_guard

    def collect_source(self, profile: SearchProfile, source: SourceConfig) -> list[Listing]:
        if self.budget_guard is not None:
            self.budget_guard.assert_can_run(
                label=f"{profile.name}/{source.name}",
                estimated_cost_usd=source.estimated_cost_usd,
            )
        actor = self.client.actor(source.actor_id)
        run = actor.call(run_input=source.run_input, wait_secs=self.wait_secs)
        if not run or "defaultDatasetId" not in run:
            raise ApifyCollectionError(f"Actor {source.actor_id} did not return a dataset id.")

        dataset_id = run["defaultDatasetId"]
        dataset_client = self.client.dataset(dataset_id)
        page = dataset_client.list_items(limit=source.limit, clean=True)
        if isinstance(page, dict):
            items = page.get("items", [])
        else:
            items = getattr(page, "items", [])
        listings = [normalize_apify_item(item, source.name, profile.transaction) for item in items]
        return listings

    def collect_profile(self, profile: SearchProfile) -> list[Listing]:
        all_listings: list[Listing] = []
        for source in profile.sources:
            listings = self.collect_source(profile, source)
            all_listings.extend(listings)
        return all_listings
