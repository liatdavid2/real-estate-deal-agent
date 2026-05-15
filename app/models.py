from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

TransactionType = Literal["sale", "rent", "unknown"]


class Listing(BaseModel):
    source: str
    listing_id: str
    title: str = ""
    city: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    address: str | None = None
    price: int | None = None
    rooms: float | None = None
    size_sqm: float | None = None
    floor: int | None = None
    total_floors: int | None = None
    transaction: TransactionType = "unknown"
    url: str | None = None
    description: str = ""
    amenities: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    contact_name: str | None = None
    contact_phone: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def price_per_sqm(self) -> int | None:
        if self.price is None or self.size_sqm in (None, 0):
            return None
        return int(round(self.price / self.size_sqm))

    @property
    def stable_key(self) -> str:
        if self.url:
            return f"{self.source}:{self.url}"
        return f"{self.source}:{self.listing_id}"

    @property
    def searchable_text(self) -> str:
        parts: list[str] = [
            self.title or "",
            self.city or "",
            self.neighborhood or "",
            self.street or "",
            self.address or "",
            self.description or "",
            " ".join(self.amenities or []),
        ]
        return " ".join(parts).lower()


class ListingEvaluation(BaseModel):
    listing: Listing
    profile_name: str
    status: Literal["new", "seen", "price_drop", "price_change"]
    score: int
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    previous_price: int | None = None
