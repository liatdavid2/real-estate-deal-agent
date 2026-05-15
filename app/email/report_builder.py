from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape

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


def build_text_report(evaluations: list[ListingEvaluation], notes: list[str] | None = None) -> str:
    lines = [f"Daily apartment deal report - {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    if notes:
        lines.append("System notes:")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")
    if not evaluations:
        lines.append("No new matching listings or price drops today.")
        return "\n".join(lines)

    for item in evaluations:
        l = item.listing
        lines.append(f"[{item.profile_name}] {l.title or l.address or l.neighborhood or l.city}")
        lines.append(f"Status: {item.status}, Score: {item.score}/100")
        lines.append(f"Price: {_money(l.price)}, Rooms: {_num(l.rooms)}, Size: {_num(l.size_sqm)} sqm, Price/sqm: {_money(l.price_per_sqm)}")
        if l.url:
            lines.append(f"URL: {l.url}")
        if item.reasons:
            lines.append("Reasons: " + "; ".join(item.reasons))
        if item.risks:
            lines.append("Check: " + "; ".join(item.risks))
        lines.append("")
    return "\n".join(lines)


def build_html_report(evaluations: list[ListingEvaluation], notes: list[str] | None = None) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    grouped: dict[str, list[ListingEvaluation]] = defaultdict(list)
    for ev in evaluations:
        grouped[ev.profile_name].append(ev)

    parts = [
        "<html><body style='font-family: Arial, sans-serif; direction: ltr;'>",
        f"<h2>Daily Apartment Deal Report</h2><p>{escape(now)}</p>",
    ]
    if notes:
        parts.append("<div style='border:1px solid #f0c36d;background:#fff8e5;border-radius:12px;padding:12px;margin:12px 0;max-width:900px;'>")
        parts.append("<b>System notes</b><ul>")
        for note in notes:
            parts.append(f"<li>{escape(note)}</li>")
        parts.append("</ul></div>")
    if not evaluations:
        parts.append("<p>No new matching listings or price drops today.</p>")
    else:
        for profile_name, items in grouped.items():
            parts.append(f"<h3>{escape(profile_name)}</h3>")
            for ev in sorted(items, key=lambda x: x.score, reverse=True):
                l = ev.listing
                title = l.title or l.address or l.neighborhood or l.city or "Apartment listing"
                url_html = f"<a href='{escape(l.url)}'>Open listing</a>" if l.url else "No URL"
                reasons = "".join(f"<li>{escape(r)}</li>" for r in ev.reasons)
                risks = "".join(f"<li>{escape(r)}</li>" for r in ev.risks)
                parts.append(
                    f"""
                    <div style="border:1px solid #ddd;border-radius:12px;padding:14px;margin:14px 0;max-width:900px;">
                      <h4 style="margin:0 0 8px 0;">{escape(title)}</h4>
                      <p style="margin:4px 0;"><b>Status:</b> {escape(ev.status)} | <b>Deal score:</b> {ev.score}/100 | <b>Source:</b> {escape(l.source)}</p>
                      <p style="margin:4px 0;"><b>Price:</b> {escape(_money(l.price))} | <b>Rooms:</b> {escape(_num(l.rooms))} | <b>Size:</b> {escape(_num(l.size_sqm))} sqm | <b>Price/sqm:</b> {escape(_money(l.price_per_sqm))}</p>
                      <p style="margin:4px 0;"><b>Location:</b> {escape(' / '.join([x for x in [l.city, l.neighborhood, l.street] if x]) or 'N/A')}</p>
                      <p>{url_html}</p>
                      <p><b>Why it looks interesting</b></p>
                      <ul>{reasons or '<li>No positive reason generated.</li>'}</ul>
                      <p><b>Verify before contacting</b></p>
                      <ul>{risks or '<li>No obvious risk found in listing text.</li>'}</ul>
                    </div>
                    """
                )
    parts.append("<p style='font-size:12px;color:#666;'>This report is an automated filter and scoring aid, not financial advice.</p>")
    parts.append("</body></html>")
    return "\n".join(parts)
