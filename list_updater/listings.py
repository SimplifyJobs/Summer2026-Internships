"""Listing data operations: loading, filtering, sorting, and validation."""

import json
from datetime import datetime
from typing import Any

from list_updater.constants import (
    BLOCKED_COMPANIES,
    LISTING_SCHEMA_PROPS,
    NON_SIMPLIFY_INACTIVE_THRESHOLD_MONTHS,
    SIMPLIFY_INACTIVE_THRESHOLD_MONTHS,
)
from list_updater.github import fail

type Listing = dict[str, Any]


def get_listings_from_json(filename: str = ".github/scripts/listings.json") -> list[Listing]:
    """Load listings from a JSON file.

    Args:
        filename: Path to the JSON file.

    Returns:
        List of listing dictionaries.
    """
    with open(filename) as f:
        listings: list[Listing] = json.load(f)
        print(f"Received {len(listings)} listings from listings.json")
        return listings


def mark_stale_listings(listings: list[Listing]) -> list[Listing]:
    """Mark listings as inactive if they exceed the age threshold.

    Args:
        listings: List of listing dictionaries.

    Returns:
        The same list with stale listings marked as inactive.
    """
    now = datetime.now()
    for listing in listings:
        age_in_months = (now - datetime.fromtimestamp(listing["date_posted"])).days / 30
        if listing["source"] != "Simplify" and age_in_months >= NON_SIMPLIFY_INACTIVE_THRESHOLD_MONTHS:
            listing["active"] = False
        elif listing["source"] == "Simplify" and age_in_months >= SIMPLIFY_INACTIVE_THRESHOLD_MONTHS:
            listing["active"] = False
    return listings


def filter_active(listings: list[Listing]) -> list[Listing]:
    """Filter to only active listings.

    Args:
        listings: List of listing dictionaries.

    Returns:
        List containing only active listings.
    """
    return [listing for listing in listings if listing.get("active", False)]


def filter_summer(listings: list[Listing], year: str, earliest_date: int) -> list[Listing]:
    """Filter listings for summer internships of a specific year.

    Args:
        listings: List of listing dictionaries.
        year: The year to filter for (e.g., "2026").
        earliest_date: Unix timestamp for the earliest allowed date.

    Returns:
        Filtered list of summer internships.
    """
    # Convert blocked URLs to lowercase for case-insensitive comparison
    blocked_urls_lower = {url.lower() for url in BLOCKED_COMPANIES}

    final_listings = []
    for listing in listings:
        if (
            listing["is_visible"]
            and any(f"Summer {year}" in item for item in listing["terms"])
            and listing["date_posted"] > earliest_date
        ):
            # Check if listing is from a blocked company
            company_url = listing.get("company_url", "").lower()
            if not any(blocked_url in company_url for blocked_url in blocked_urls_lower):
                final_listings.append(listing)

    return final_listings


def filter_off_season(listings: list[Listing]) -> list[Listing]:
    """Filter listings for off-season (Fall, Winter, Spring) internships.

    Args:
        listings: List of listing dictionaries.

    Returns:
        Filtered list of off-season internships.
    """

    def is_off_season(listing: Listing) -> bool:
        if not listing.get("is_visible"):
            return False

        terms = listing.get("terms", [])
        has_off_season_term = any(season in term for term in terms for season in ["Fall", "Winter", "Spring"])
        has_summer_term = any("Summer" in term for term in terms)

        # We don't want to include listings in the off season list if they include a Summer term
        return has_off_season_term and not has_summer_term

    return [listing for listing in listings if is_off_season(listing)]


def sort_listings(listings: list[Listing]) -> list[Listing]:
    """Sort listings by date and company.

    Args:
        listings: List of listing dictionaries.

    Returns:
        Sorted list of listings.
    """
    oldest_listing_from_company: dict[str, int] = {}
    link_for_company: dict[str, str] = {}

    for listing in listings:
        date_posted = listing["date_posted"]
        company_lower = listing["company_name"].lower()
        if company_lower not in oldest_listing_from_company or oldest_listing_from_company[company_lower] > date_posted:
            oldest_listing_from_company[company_lower] = date_posted
        if listing["company_name"] not in link_for_company or len(listing["company_url"]) > 0:
            link_for_company[listing["company_name"]] = listing["company_url"]

    listings.sort(
        key=lambda x: (
            x["active"],  # Active listings first
            x["date_posted"],
            x["company_name"].lower(),
            x["date_updated"],
        ),
        reverse=True,
    )

    for listing in listings:
        listing["company_url"] = link_for_company[listing["company_name"]]

    return listings


def check_schema(listings: list[Listing]) -> None:
    """Validate that all listings have required properties.

    Args:
        listings: List of listing dictionaries.

    Raises:
        SystemExit: If any listing is missing a required property.
    """
    for listing in listings:
        for prop in LISTING_SCHEMA_PROPS:
            if prop not in listing:
                fail(f"ERROR: Schema check FAILED - object with id {listing['id']} does not contain prop '{prop}'")
