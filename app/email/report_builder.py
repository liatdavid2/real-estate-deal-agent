from __future__ import annotations

import re
from datetime import datetime
from html import escape
from typing import Any

from app.models import ListingEvaluation


def _money(value: int | float | None) -> str:
    if value is None:
        return "N/A"

    return f"{int(value):,} ₪"


def _num(value: float | int | None) -> str:
    if value is None:
        return "N/A"

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""

    return re.sub(r"\s+", " ", value).strip()


def _listing_text(listing: Any) -> str:
    parts = [
        getattr(listing, "title", None),
        getattr(listing, "address", None),
        getattr(listing, "city", None),
        getattr(listing, "neighborhood", None),
        getattr(listing, "street", None),
        getattr(listing, "description", None),
        getattr(listing, "searchable_text", None),
    ]

    return _clean_text(" ".join(str(part) for part in parts if part))

def _description(listing: Any, max_len: int = 220) -> str:
    description = getattr(listing, "description", None)

    text = _clean_text(str(description or ""))

    bad_values = {
        "",
        "n/a",
        "none",
        "null",
        "givatayim",
        "haifa",
        "גבעתיים",
        "חיפה",
    }

    if text.lower() in bad_values:
        return "לא צויין"

    # If the text is too short, it is probably only a title, street, city, or neighborhood.
    if len(text) < 30:
        return "לא צויין"

    # If the description is mostly just location/title text, do not show it as a description.
    title = _clean_text(str(getattr(listing, "title", "") or ""))
    address = _clean_text(str(getattr(listing, "address", "") or ""))
    city = _clean_text(str(getattr(listing, "city", "") or ""))
    neighborhood = _clean_text(str(getattr(listing, "neighborhood", "") or ""))
    street = _clean_text(str(getattr(listing, "street", "") or ""))

    location_parts = [title, address, city, neighborhood, street]
    location_parts = [part for part in location_parts if part]

    if text in location_parts:
        return "לא צויין"

    if len(text) > max_len:
        return text[:max_len].rstrip() + "..."

    return text

def _address(listing: Any) -> str:
    title = getattr(listing, "title", None)
    address = getattr(listing, "address", None)
    city = getattr(listing, "city", None)
    neighborhood = getattr(listing, "neighborhood", None)
    street = getattr(listing, "street", None)

    if address:
        return str(address)

    location_parts = [part for part in [street, neighborhood, city] if part]
    if location_parts:
        return " / ".join(str(part) for part in location_parts)

    if title:
        return str(title)

    return "N/A"


def _address_html(listing: Any) -> str:
    address = _address(listing)
    url = getattr(listing, "url", None)

    if url:
        return f"<a href='{escape(str(url))}'>{escape(address)}</a>"

    return escape(address)


def _floor(listing: Any) -> str:
    floor = getattr(listing, "floor", None)
    if floor is not None:
        return _num(floor)

    text = _listing_text(listing)

    patterns = [
        r"קומה\s*[:\-]?\s*(-?\d+)",
        r"floor\s*[:\-]?\s*(-?\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    if "קרקע" in text:
        return "קרקע"

    return "N/A"


def _yes_no_from_text(
    listing: Any,
    positive_keywords: list[str],
    negative_keywords: list[str],
) -> str:
    text = _listing_text(listing).lower()

    for keyword in negative_keywords:
        if keyword.lower() in text:
            return "לא"

    for keyword in positive_keywords:
        if keyword.lower() in text:
            return "כן"

    return "לא צויין"


def _parking(listing: Any) -> str:
    return _yes_no_from_text(
        listing,
        positive_keywords=[
            "חניה",
            "חנייה",
            "parking",
            "חניה בטאבו",
            "חנייה בטאבו",
        ],
        negative_keywords=[
            "ללא חניה",
            "ללא חנייה",
            "בלי חניה",
            "בלי חנייה",
            "אין חניה",
            "אין חנייה",
            "ללא parking",
            "no parking",
        ],
    )


def _elevator(listing: Any) -> str:
    return _yes_no_from_text(
        listing,
        positive_keywords=[
            "מעלית",
            "elevator",
        ],
        negative_keywords=[
            "ללא מעלית",
            "בלי מעלית",
            "אין מעלית",
            "no elevator",
        ],
    )


def _rental_info(listing: Any) -> str:
    text = _listing_text(listing)

    rented_keywords = [
        "מושכרת",
        "מושכר",
        "שוכר",
        "שוכרים",
        "שכירות",
        "שכר דירה",
        "תשואה",
        "rented",
        "rent",
    ]

    is_rented = any(keyword.lower() in text.lower() for keyword in rented_keywords)

    if not is_rented:
        return "לא צויין"

    patterns = [
        r"מושכרת\s*(?:ב|ב-|ב־)?\s*([\d,]{3,6})",
        r"מושכר\s*(?:ב|ב-|ב־)?\s*([\d,]{3,6})",
        r"שכירות\s*(?:של|ב|ב-|ב־)?\s*([\d,]{3,6})",
        r"שכר\s*דירה\s*(?:של|ב|ב-|ב־)?\s*([\d,]{3,6})",
        r"רנט\s*(?:של|ב|ב-|ב־)?\s*([\d,]{3,6})",
        r"rent\s*(?:of|for|at)?\s*([\d,]{3,6})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            rent = match.group(1).replace(",", "")
            try:
                return f"כן, {_money(int(rent))}"
            except ValueError:
                return f"כן, {match.group(1)} ₪"

    return "כן, מחיר לא צויין"


def _row_from_evaluation(item: ListingEvaluation) -> dict[str, Any]:
    return {
        "profile_name": item.profile_name,
        "listing": item.listing,
        "score": item.score,
        "status": item.status,
        "filter_status": "Matched",
        "filter_failures": [],
    }


def _row_from_raw_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_name": item.get("profile_name", ""),
        "listing": item["listing"],
        "score": None,
        "status": "",
        "filter_status": "Matched" if item.get("filter_ok") else "Filtered out",
        "filter_failures": item.get("filter_failures") or [],
    }


def _make_rows(
    evaluations: list[ListingEvaluation],
    raw_items: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    # Prefer raw_items so the email always shows every collected apartment,
    # including listings that were filtered out and the reason why.
    if raw_items:
        return [_row_from_raw_item(item) for item in raw_items]

    if evaluations:
        return [_row_from_evaluation(item) for item in evaluations]

    return []


def build_text_report(
    evaluations: list[ListingEvaluation],
    notes: list[str] | None = None,
    raw_items: list[dict[str, Any]] | None = None,
) -> str:
    rows = _make_rows(evaluations, raw_items)

    lines = [
        f"Daily apartment deal report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if notes:
        lines.append("System notes:")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    if not rows:
        lines.append("No listings collected.")
        return "\n".join(lines)

    lines.append("Apartments:")
    lines.append("")

    for row in rows:
        listing = row["listing"]
        failures = row.get("filter_failures") or []

        lines.append(
            " | ".join(
                [
                    f"Price: {_money(getattr(listing, 'price', None))}",
                    f"Address: {_address(listing)}",
                    f"Rooms: {_num(getattr(listing, 'rooms', None))}",
                    f"Floor: {_floor(listing)}",
                    f"Parking: {_parking(listing)}",
                    f"Elevator: {_elevator(listing)}",
                    f"Rent: {_rental_info(listing)}",
                    f"Description: {_description(listing, max_len=300)}",
                ]
            )
        )

        url = getattr(listing, "url", None)
        if url:
            lines.append(f"URL: {url}")

        if failures:
            lines.append("Filtered out: " + "; ".join(failures))

        lines.append("")

    lines.append("This report is an automated filter and scoring aid, not financial advice.")

    return "\n".join(lines)


def build_html_report(
    evaluations: list[ListingEvaluation],
    notes: list[str] | None = None,
    raw_items: list[dict[str, Any]] | None = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = _make_rows(evaluations, raw_items)

    parts = [
        "<html>",
        "<body style='font-family:Arial,sans-serif;direction:rtl;text-align:right;margin:0;padding:12px;'>",
        "<h3 style='margin:0 0 8px 0;'>Daily Apartment Deal Report</h3>",
        f"<p style='margin:0 0 12px 0;font-size:12px;color:#666;'>{escape(now)}</p>",
    ]

    if notes:
        parts.append(
            "<div style='border:1px solid #f0c36d;background:#fff8e5;"
            "border-radius:8px;padding:8px;margin:8px 0;font-size:12px;'>"
        )
        parts.append("<b>System notes</b><ul style='margin:6px 0;'>")

        for note in notes:
            parts.append(f"<li>{escape(note)}</li>")

        parts.append("</ul></div>")

    if not rows:
        parts.append("<p>No listings collected.</p>")
    else:
        if evaluations:
            parts.append(
                f"<p style='font-size:12px;margin:0 0 8px 0;'>"
                f"Matched listings: {len(evaluations)}</p>"
            )
        else:
            parts.append(
                f"<p style='font-size:12px;margin:0 0 8px 0;'>"
                f"No matching listings. Showing collected listings before filtering: {len(rows)}</p>"
            )

        parts.append(
            """
            <table style="
                border-collapse:collapse;
                width:100%;
                font-size:12px;
                table-layout:fixed;
            ">
              <thead>
                <tr style="background:#f4f4f4;">
                  <th style="border:1px solid #ddd;padding:5px;width:12%;">מחיר</th>
                  <th style="border:1px solid #ddd;padding:5px;width:24%;">כתובת</th>
                  <th style="border:1px solid #ddd;padding:5px;width:8%;">חדרים</th>
                  <th style="border:1px solid #ddd;padding:5px;width:8%;">קומה</th>
                  <th style="border:1px solid #ddd;padding:5px;width:8%;">חניה</th>
                  <th style="border:1px solid #ddd;padding:5px;width:8%;">מעלית</th>
                  <th style="border:1px solid #ddd;padding:5px;width:14%;">שכירות</th>
                  <th style="border:1px solid #ddd;padding:5px;width:28%;">תיאור</th>
                  <th style="border:1px solid #ddd;padding:5px;width:8%;">סטטוס</th>
                </tr>
              </thead>
              <tbody>
            """
        )

        for row in rows:
            listing = row["listing"]
            failures = row.get("filter_failures") or []
            filter_status = row.get("filter_status") or ""
            is_filtered_out = filter_status == "Filtered out"

            status_text = "נפל" if is_filtered_out else "עבר"
            if failures:
                status_text += ": " + "; ".join(str(failure) for failure in failures)

            background = "#fff" if is_filtered_out else "#eefaf0"

            parts.append(
                f"""
                <tr style="background:{background};">
                  <td style="border:1px solid #ddd;padding:5px;white-space:nowrap;">{escape(_money(getattr(listing, "price", None)))}</td>
                  <td style="border:1px solid #ddd;padding:5px;overflow:hidden;text-overflow:ellipsis;">{_address_html(listing)}</td>
                  <td style="border:1px solid #ddd;padding:5px;text-align:center;">{escape(_num(getattr(listing, "rooms", None)))}</td>
                  <td style="border:1px solid #ddd;padding:5px;text-align:center;">{escape(_floor(listing))}</td>
                  <td style="border:1px solid #ddd;padding:5px;text-align:center;">{escape(_parking(listing))}</td>
                  <td style="border:1px solid #ddd;padding:5px;text-align:center;">{escape(_elevator(listing))}</td>
                  <td style="border:1px solid #ddd;padding:5px;white-space:nowrap;">{escape(_rental_info(listing))}</td>
                  <td style="border:1px solid #ddd;padding:5px;font-size:11px;line-height:1.35;">{escape(_description(listing))}</td>
                  <td style="border:1px solid #ddd;padding:5px;font-size:11px;">{escape(status_text)}</td>
                </tr>
                """
            )

        parts.append("</tbody></table>")

    parts.append(
        "<p style='font-size:11px;color:#666;margin-top:10px;'>"
        "This report is an automated filter and scoring aid, not financial advice."
        "</p>"
    )
    parts.append("</body></html>")

    return "\n".join(parts)