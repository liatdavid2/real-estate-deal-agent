from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from app.agents.deal_score_agent import score_listing
from app.agents.filter_agent import filter_listings
from app.budget.apify_budget import ApifyBudgetGuard, BudgetExceededError, BudgetGuardError
from app.collectors.apify_collector import ApifyRealEstateCollector
from app.config import SearchProfile, load_config
from app.email.report_builder import build_html_report, build_text_report
from app.email.senders import send_email
from app.models import ListingEvaluation
from app.storage.sqlite_store import SQLiteListingStore


def _select_profiles(profiles: list[SearchProfile], names: list[str] | None, all_profiles: bool) -> list[SearchProfile]:
    enabled = [p for p in profiles if p.enabled]
    if all_profiles:
        return enabled
    if names:
        requested = set(names)
        return [p for p in enabled if p.name in requested]
    if enabled:
        return [enabled[0]]
    return []


def run(config_path: str, profile_names: list[str] | None, all_profiles: bool, send: bool, include_existing: bool) -> list[ListingEvaluation]:
    load_dotenv()
    config = load_config(config_path)
    profiles = _select_profiles(config.profiles, profile_names, all_profiles)
    if not profiles:
        raise RuntimeError("No enabled search profiles selected.")

    sqlite_path = config.settings.get("sqlite_path") or os.getenv("SQLITE_PATH", "data/real_estate_agent.db")
    artifacts_dir = config.settings.get("artifacts_dir") or os.getenv("ARTIFACTS_DIR", "artifacts")
    subject_prefix = config.settings.get("email_subject_prefix", "Daily Apartment Deals")

    budget_guard = ApifyBudgetGuard()
    budget_notes: list[str] = []
    try:
        if budget_guard.enabled and budget_guard.enable_platform_hard_limit:
            budget_notes.append(budget_guard.set_platform_hard_limit())
    except BudgetGuardError as exc:
        budget_notes.append(f"Could not set Apify platform hard limit: {exc}")

    collector = ApifyRealEstateCollector(budget_guard=budget_guard)
    store = SQLiteListingStore(sqlite_path)
    evaluations: list[ListingEvaluation] = []

    try:
        for profile in profiles:
            print(f"Collecting profile: {profile.name}")
            try:
                raw_listings = collector.collect_profile(profile)
            except BudgetExceededError as exc:
                note = f"Budget guard stopped collection for {profile.name}: {exc}"
                print(note)
                budget_notes.append(note)
                break
            except BudgetGuardError as exc:
                note = f"Budget guard could not verify Apify usage for {profile.name}: {exc}"
                print(note)
                budget_notes.append(note)
                break
            print(f"Collected {len(raw_listings)} listings before filtering for {profile.name}")
            matched = filter_listings(raw_listings, profile)
            print(f"Matched {len(matched)} listings after filtering for {profile.name}")

            for listing in matched:
                status, previous_price = store.upsert_listing(profile.name, listing)
                if status == "seen" and not include_existing:
                    continue
                score, reasons, risks = score_listing(listing, profile, status=status, previous_price=previous_price)
                evaluations.append(
                    ListingEvaluation(
                        listing=listing,
                        profile_name=profile.name,
                        status=status,
                        score=score,
                        reasons=reasons,
                        risks=risks,
                        previous_price=previous_price,
                    )
                )
    finally:
        store.close()

    evaluations.sort(key=lambda ev: ev.score, reverse=True)
    html_body = build_html_report(evaluations, notes=budget_notes)
    text_body = build_text_report(evaluations, notes=budget_notes)
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(artifacts_dir, "latest_report.html").write_text(html_body, encoding="utf-8")
    Path(artifacts_dir, "latest_report.txt").write_text(text_body, encoding="utf-8")

    if send:
        subject = f"{subject_prefix} - {len(evaluations)} updates"
        send_email(subject, html_body, text_body, artifacts_dir)
    else:
        print(text_body)
        print(f"Report written to {Path(artifacts_dir, 'latest_report.html')}")

    return evaluations


def main() -> None:
    parser = argparse.ArgumentParser(description="Real Estate Deal Finder Agent")
    parser.add_argument("--config", default="configs/searches.yaml")
    parser.add_argument("--profile", action="append", dest="profiles", help="Profile name. Can be repeated.")
    parser.add_argument("--all-profiles", action="store_true")
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--include-existing", action="store_true", help="Send all current matches, useful for the first run.")
    args = parser.parse_args()

    run(
        config_path=args.config,
        profile_names=args.profiles,
        all_profiles=args.all_profiles,
        send=args.send_email,
        include_existing=args.include_existing,
    )


if __name__ == "__main__":
    main()
