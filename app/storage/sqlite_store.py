from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.models import Listing

ListingStatus = Literal["new", "seen", "price_drop", "price_change"]


class SQLiteListingStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                profile_name TEXT NOT NULL,
                stable_key TEXT NOT NULL,
                source TEXT NOT NULL,
                listing_id TEXT NOT NULL,
                url TEXT,
                title TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_price INTEGER,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (profile_name, stable_key)
            )
            """
        )
        self.conn.commit()

    def upsert_listing(self, profile_name: str, listing: Listing) -> tuple[ListingStatus, int | None]:
        now = datetime.now(timezone.utc).isoformat()
        key = listing.stable_key
        row = self.conn.execute(
            "SELECT last_price FROM listings WHERE profile_name = ? AND stable_key = ?",
            (profile_name, key),
        ).fetchone()

        payload_json = listing.model_dump_json(exclude={"raw"})
        if row is None:
            self.conn.execute(
                """
                INSERT INTO listings (
                    profile_name, stable_key, source, listing_id, url, title,
                    first_seen_at, last_seen_at, last_price, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_name,
                    key,
                    listing.source,
                    listing.listing_id,
                    listing.url,
                    listing.title,
                    now,
                    now,
                    listing.price,
                    payload_json,
                ),
            )
            self.conn.commit()
            return "new", None

        previous_price = row["last_price"]
        status: ListingStatus = "seen"
        if previous_price is not None and listing.price is not None:
            if listing.price < previous_price:
                status = "price_drop"
            elif listing.price != previous_price:
                status = "price_change"

        self.conn.execute(
            """
            UPDATE listings
            SET last_seen_at = ?, last_price = ?, payload_json = ?
            WHERE profile_name = ? AND stable_key = ?
            """,
            (now, listing.price, payload_json, profile_name, key),
        )
        self.conn.commit()
        return status, previous_price

    def close(self) -> None:
        self.conn.close()
