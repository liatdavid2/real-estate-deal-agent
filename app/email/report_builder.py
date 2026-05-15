from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Any

from app.models import ListingEvaluation


def _money(value: int | None) -> str:
    if value is None:
        return "N/A"

    return f"{value:,} ILS"


def _num(value: float | int | None) -> str:
    if value is None:
        return "N/A"

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def build_text_report(
    evaluations: list[ListingEvaluation],
    notes: list[str] | None = None,
    raw_items: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        f"Daily apartment deal report - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if notes:
        lines.append("System notes:")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    if not evaluations:
        lines.append("No new matching listings or price drops today.")
        lines.append("")
    else:
        lines.append("Matched listings:")
        lines.append("")

        for item in evaluations:
            listing = item.listing
            title = (
                listing.title
                or listing.address
                or listing.neighborhood
                or listing.city
                or "Apartment listing"
            )

            lines.append(f"[{item.profile_name}] {title}")
            lines.append(f"Status: {item.status}, Score: {item.score}/100")
            lines.append(
                f"Price: {_money(listing.price)}, "
                f"Rooms: {_num(listing.rooms)}, "
                f"Size: {_num(listing.size_sqm)} sqm, "
                f"Price/sqm: {_money(listing.price_per_sqm)}"
            )

            if listing.url:
                lines.append(f"URL: {listing.url}")

            if item.reasons:
                lines.append("Reasons: " + "; ".join(item.reasons))

            if item.risks:
                lines.append("Check: " + "; ".join(item.risks))

            lines.append("")

    if raw_items:
        lines.append("Collected listings before filtering:")
        lines.append("")

        for item in raw_items:
            listing = item["listing"]
            failures = item.get("filter_failures") or []
            status = "MATCHED FILTERS" if item.get("filter_ok") else "FILTERED OUT"

            title = (
                listing.title
                or listing.address
                or listing.neighborhood
                or listing.city
                or "Apartment listing"
            )

            lines.append(f"[{item['profile_name']}] {title}")
            lines.append(f"Filter status: {status}")
            lines.append(
                f"Source: {listing.source}, "
                f"Price: {_money(listing.price)}, "
                f"Rooms: {_num(listing.rooms)}, "
                f"Size: {_num(listing.size_sqm)} sqm, "
                f"City: {listing.city or 'N/A'}"
            )

            if failures:
                lines.append("Why filtered out: " + "; ".join(failures))

            if listing.url:
                lines.append(f"URL: {listing.url}")

            lines.append("")

    lines.append("This report is an automated filter and scoring aid, not financial advice.")

    return "\n".join(lines)


def build_html_report(
    evaluations: list[ListingEvaluation],
    notes: list[str] | None = None,
    raw_items: list[dict[str, Any]] | None = None,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    grouped: dict[str, list[ListingEvaluation]] = defaultdict(list)
    for evaluation in evaluations:
        grouped[evaluation.profile_name].append(evaluation)

    parts = [
        "<html>",
        "<body style='font-family: Arial, sans-serif; direction: ltr;'>",
        "<h2>Daily Apartment Deal Report</h2>",
        f"<p>{escape(now)}</p>",
    ]

    if notes:
        parts.append(
            "<div style='border:1px solid #f0c36d;background:#fff8e5;"
            "border-radius:12px;padding:12px;margin:12px 0;max-width:1100px;'>"
        )
        parts.append("<b>System notes</b><ul>")

        for note in notes:
            parts.append(f"<li>{escape(note)}</li>")

        parts.append("</ul></div>")

    if not evaluations:
        parts.append("<p>No new matching listings or price drops today.</p>")
    else:
        parts.append("<h3>Matched listings</h3>")

        for profile_name, items in grouped.items():
            parts.append(f"<h4>{escape(profile_name)}</h4>")

            for evaluation in sorted(items, key=lambda x: x.score, reverse=True):
                listing = evaluation.listing

                title = (
                    listing.title
                    or listing.address
                    or listing.neighborhood
                    or listing.city
                    or "Apartment listing"
                )

                url_html = (
                    f"<a href='{escape(listing.url)}'>Open listing</a>"
                    if listing.url
                    else "No URL"
                )

                reasons = "".join(f"<li>{escape(reason)}</li>" for reason in evaluation.reasons)
                risks = "".join(f"<li>{escape(risk)}</li>" for risk in evaluation.risks)

                location = " / ".join(
                    value for value in [listing.city, listing.neighborhood, listing.street] if value
                ) or "N/A"

                parts.append(
                    f"""
                    <div style="border:1px solid #ddd;border-radius:12px;padding:14px;margin:14px 0;max-width:1100px;">
                      <h4 style="margin:0 0 8px 0;">{escape(title)}</h4>
                      <p style="margin:4px 0;">
                        <b>Status:</b> {escape(evaluation.status)}
                        |
                        <b>Deal score:</b> {evaluation.score}/100
                        |
                        <b>Source:</b> {escape(listing.source)}
                      </p>
                      <p style="margin:4px 0;">
                        <b>Price:</b> {escape(_money(listing.price))}
                        |
                        <b>Rooms:</b> {escape(_num(listing.rooms))}
                        |
                        <b>Size:</b> {escape(_num(listing.size_sqm))} sqm
                        |
                        <b>Price/sqm:</b> {escape(_money(listing.price_per_sqm))}
                      </p>
                      <p style="margin:4px 0;"><b>Location:</b> {escape(location)}</p>
                      <p>{url_html}</p>
                      <p><b>Why it looks interesting</b></p>
                      <ul>{reasons or "<li>No positive reason generated.</li>"}</ul>
                      <p><b>Verify before contacting</b></p>
                      <ul>{risks or "<li>No obvious risk found in listing text.</li>"}</ul>
                    </div>
                    """
                )

    if raw_items:
        parts.append("<h3>Collected listings before filtering</h3>")
        parts.append(
            """
            <table style="border-collapse:collapse;width:100%;max-width:1200px;font-size:13px;">
              <thead>
                <tr style="background:#f4f4f4;">
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Profile</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Source</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Listing</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Price</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Rooms</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Size</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Filter status</th>
                  <th style="border:1px solid #ddd;padding:8px;text-align:left;">Why filtered out</th>
                </tr>
              </thead>
              <tbody>
            """
        )

        for item in raw_items:
            listing = item["listing"]
            failures = item.get("filter_failures") or []
            filter_ok = bool(item.get("filter_ok"))

            title = (
                listing.title
                or listing.address
                or listing.neighborhood
                or listing.city
                or "Apartment listing"
            )

            if listing.url:
                title_html = f"<a href='{escape(listing.url)}'>{escape(title)}</a>"
            else:
                title_html = escape(title)

            location = " / ".join(
                value for value in [listing.city, listing.neighborhood, listing.street] if value
            )

            if location:
                title_html += (
                    f"<br><span style='color:#666;font-size:12px;'>"
                    f"{escape(location)}"
                    f"</span>"
                )

            status = "Matched filters" if filter_ok else "Filtered out"
            failures_text = "; ".join(failures) if failures else ""

            row_background = "#eefaf0" if filter_ok else "#fff"

            parts.append(
                f"""
                <tr style="background:{row_background};">
                  <td style="border:1px solid #ddd;padding:8px;">{escape(item["profile_name"])}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(listing.source or "N/A")}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{title_html}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(_money(listing.price))}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(_num(listing.rooms))}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(_num(listing.size_sqm))} sqm</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(status)}</td>
                  <td style="border:1px solid #ddd;padding:8px;">{escape(failures_text)}</td>
                </tr>
                """
            )

        parts.append("</tbody></table>")

    parts.append(
        "<p style='font-size:12px;color:#666;margin-top:18px;'>"
        "This report is an automated filter and scoring aid, not financial advice."
        "</p>"
    )
    parts.append("</body></html>")

    return "\n".join(parts)