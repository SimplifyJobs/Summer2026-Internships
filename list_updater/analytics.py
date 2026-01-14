"""Analytics and debugging commands for listings."""

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from typing import Any

from list_updater.category import classify_job_category
from list_updater.constants import BLOCKED_COMPANIES, CATEGORIES, LISTING_SCHEMA_PROPS

# Note: classify_job_category is used in cmd_listings_fix for category suggestions
from list_updater.listings import get_listings_from_json

LISTINGS_JSON_PATH = ".github/scripts/listings.json"

type Listing = dict[str, Any]


# =============================================================================
# Stats Command
# =============================================================================


def cmd_listings_stats(json_output: bool = False) -> None:
    """Show listing statistics.

    Args:
        json_output: If True, output as JSON instead of formatted text.
    """
    listings = get_listings_from_json()

    # Basic counts
    total = len(listings)
    active = sum(1 for listing in listings if listing.get("active", False))
    inactive = total - active
    visible = sum(1 for listing in listings if listing.get("is_visible", True))
    hidden = total - visible

    # Category breakdown
    category_counts: Counter[str] = Counter()
    for listing in listings:
        cat = listing.get("category", "Other")
        category_counts[cat] += 1

    # Top companies by listing count
    company_counts: Counter[str] = Counter()
    for listing in listings:
        company_counts[listing["company_name"]] += 1
    top_companies = company_counts.most_common(10)

    # Sponsorship breakdown
    sponsorship_counts: Counter[str] = Counter()
    for listing in listings:
        sponsorship_counts[listing.get("sponsorship", "Unknown")] += 1

    # Source breakdown
    source_counts: Counter[str] = Counter()
    for listing in listings:
        source_counts[listing.get("source", "Unknown")] += 1

    stats = {
        "total": total,
        "active": active,
        "inactive": inactive,
        "visible": visible,
        "hidden": hidden,
        "by_category": dict(category_counts),
        "by_sponsorship": dict(sponsorship_counts),
        "by_source": dict(source_counts),
        "top_companies": [{"company": c, "count": n} for c, n in top_companies],
    }

    if json_output:
        print(json.dumps(stats, indent=2))
        return

    # Formatted output
    print("=" * 60)
    print("LISTING STATISTICS")
    print("=" * 60)
    print(f"\nTotal Listings: {total}")
    print(f"  Active: {active} ({active / total * 100:.1f}%)")
    print(f"  Inactive: {inactive} ({inactive / total * 100:.1f}%)")
    print(f"  Visible: {visible}")
    print(f"  Hidden: {hidden}")

    print("\nBy Category:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        cat_info = CATEGORIES.get(cat, {})
        emoji = cat_info.get("emoji", "📋")
        print(f"  {emoji} {cat}: {count}")

    print("\nBy Sponsorship:")
    for sponsor, count in sorted(sponsorship_counts.items(), key=lambda x: -x[1]):
        print(f"  {sponsor}: {count}")

    print("\nTop 10 Companies:")
    for i, (company, count) in enumerate(top_companies, 1):
        print(f"  {i}. {company}: {count} listings")

    print("\nBy Source:")
    for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count}")


# =============================================================================
# Validate Command
# =============================================================================


def cmd_listings_validate(fix: bool = False) -> None:
    """Validate listings.json schema and data integrity.

    Args:
        fix: If True, attempt to auto-fix issues where possible.
    """
    listings = get_listings_from_json()
    issues: list[str] = []
    warnings: list[str] = []
    fixed: list[str] = []

    # Check for required schema properties
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")

        for prop in LISTING_SCHEMA_PROPS:
            if prop not in listing:
                issues.append(f"[{company}] Missing required property: {prop} (id: {listing_id})")

    # Check for duplicate URLs
    url_counts: Counter[str] = Counter()
    for listing in listings:
        url = listing.get("url", "")
        if url:
            url_counts[url] += 1

    for url, count in url_counts.items():
        if count > 1:
            issues.append(f"Duplicate URL found {count} times: {url}")

    # Check for duplicate IDs
    id_counts: Counter[str] = Counter()
    for listing in listings:
        listing_id = listing.get("id", "")
        if listing_id:
            id_counts[listing_id] += 1

    for listing_id, count in id_counts.items():
        if count > 1:
            issues.append(f"Duplicate ID found {count} times: {listing_id}")

    # Check for valid dates
    now = datetime.now().timestamp()
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")

        date_posted = listing.get("date_posted", 0)
        if date_posted > now:
            warnings.append(f"[{company}] Future date_posted: {datetime.fromtimestamp(date_posted)} (id: {listing_id})")

        date_updated = listing.get("date_updated", 0)
        if date_updated > now:
            warnings.append(
                f"[{company}] Future date_updated: {datetime.fromtimestamp(date_updated)} (id: {listing_id})"
            )

    # Check for empty required fields
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")

        if not listing.get("title", "").strip():
            issues.append(f"[{company}] Empty title (id: {listing_id})")

        if not listing.get("url", "").strip():
            issues.append(f"[{company}] Empty URL (id: {listing_id})")

        if not listing.get("locations"):
            warnings.append(f"[{company}] No locations specified (id: {listing_id})")

    # Check for valid category
    valid_categories = set(CATEGORIES.keys()) | {cat["name"] for cat in CATEGORIES.values()} | {"Other"}
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")
        category = listing.get("category")

        # Missing or None category
        if category is None or category == "None":
            warnings.append(f"[{company}] Missing/None category (id: {listing_id})")
        elif category not in valid_categories:
            warnings.append(f"[{company}] Unknown category: {category} (id: {listing_id})")

    # Check for empty terms (would be filtered out)
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")
        terms = listing.get("terms", [])

        if not terms:
            warnings.append(f"[{company}] Empty terms list - will be filtered from README (id: {listing_id})")

    # Check for blocked companies
    blocked_urls_lower = {url.lower() for url in BLOCKED_COMPANIES}
    for listing in listings:
        listing_id = listing.get("id", "unknown")
        company = listing.get("company_name", "unknown")
        company_url = listing.get("company_url", "").lower()

        if any(blocked_url in company_url for blocked_url in blocked_urls_lower):
            warnings.append(f"[{company}] Blocked company URL - will be filtered from README (id: {listing_id})")

    # Print results
    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    if issues:
        print(f"\n❌ ERRORS ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ No errors found!")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    if fixed:
        print(f"\n🔧 FIXED ({len(fixed)}):")
        for f in fixed:
            print(f"  - {f}")

    print(f"\nTotal: {len(listings)} listings checked")
    print(f"Errors: {len(issues)}, Warnings: {len(warnings)}, Fixed: {len(fixed)}")

    # Count filtering issues for summary
    filter_issues = [w for w in warnings if "will be filtered" in w]
    if filter_issues:
        print(f"\n📋 FILTERING ISSUES ({len(filter_issues)}):")
        print("   These listings will be excluded from README generation.")

    if issues:
        print("\nRun 'listings fix' to interactively fix issues.")
        sys.exit(1)


# =============================================================================
# Search Command
# =============================================================================


def cmd_listings_search(
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    category: str | None = None,
    active_only: bool = False,
    inactive_only: bool = False,
    limit: int = 20,
) -> None:
    """Search and filter listings.

    Args:
        company: Filter by company name (case-insensitive substring match).
        title: Filter by job title (case-insensitive substring match).
        location: Filter by location (case-insensitive substring match).
        category: Filter by category (case-insensitive substring match).
        active_only: Show only active listings.
        inactive_only: Show only inactive listings.
        limit: Maximum number of results to show.
    """
    listings = get_listings_from_json()
    results: list[Listing] = []

    for listing in listings:
        # Apply filters
        if company and company.lower() not in listing.get("company_name", "").lower():
            continue
        if title and title.lower() not in listing.get("title", "").lower():
            continue
        if location:
            locations = listing.get("locations", [])
            if not any(location.lower() in loc.lower() for loc in locations):
                continue
        if category and category.lower() not in listing.get("category", "").lower():
            continue
        if active_only and not listing.get("active", False):
            continue
        if inactive_only and listing.get("active", False):
            continue

        results.append(listing)

    # Sort by date_posted descending
    results.sort(key=lambda x: x.get("date_posted", 0), reverse=True)

    # Limit results
    results = results[:limit]

    print(f"Found {len(results)} matching listings")
    print("=" * 80)

    for listing in results:
        status = "✅" if listing.get("active") else "❌"
        company_name = listing.get("company_name", "Unknown")
        job_title = listing.get("title", "Unknown")
        locations = ", ".join(listing.get("locations", ["Unknown"]))
        cat = listing.get("category", "Other")
        date = datetime.fromtimestamp(listing.get("date_posted", 0)).strftime("%Y-%m-%d")

        print(f"{status} [{cat}] {company_name}")
        print(f"   {job_title}")
        print(f"   📍 {locations}")
        print(f"   📅 Posted: {date}")
        print(f"   🔗 {listing.get('url', 'N/A')}")
        print()


# =============================================================================
# Diff Command
# =============================================================================


def cmd_listings_diff(since: str | None = None, commit: str | None = None) -> None:
    """Show changes to listings since a date or commit.

    Args:
        since: Show changes since this date (YYYY-MM-DD format).
        commit: Show changes since this git commit hash.
    """
    listings = get_listings_from_json()

    if commit:
        # Get listings from a specific commit
        try:
            result = subprocess.run(
                ["git", "show", f"{commit}:.github/scripts/listings.json"],
                capture_output=True,
                text=True,
                check=True,
            )
            old_listings: list[Listing] = json.loads(result.stdout)
        except subprocess.CalledProcessError:
            print(f"❌ Could not retrieve listings from commit: {commit}")
            return
        except json.JSONDecodeError:
            print(f"❌ Could not parse listings from commit: {commit}")
            return
    elif since:
        # Filter by date
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d")
            since_timestamp = since_date.timestamp()
        except ValueError:
            print(f"❌ Invalid date format: {since}. Use YYYY-MM-DD.")
            return

        # Show listings added or updated since the date
        added = []
        updated = []

        for listing in listings:
            date_posted = listing.get("date_posted", 0)
            date_updated = listing.get("date_updated", 0)

            if date_posted >= since_timestamp:
                added.append(listing)
            elif date_updated >= since_timestamp:
                updated.append(listing)

        print(f"Changes since {since}")
        print("=" * 60)

        if added:
            print(f"\n➕ ADDED ({len(added)}):")
            for listing in added[:20]:  # Limit output
                print(f"  - {listing['company_name']}: {listing['title']}")

        if updated:
            print(f"\n📝 UPDATED ({len(updated)}):")
            for listing in updated[:20]:  # Limit output
                status = "active" if listing.get("active") else "inactive"
                print(f"  - {listing['company_name']}: {listing['title']} ({status})")

        if not added and not updated:
            print("\nNo changes found since the specified date.")

        return

    # Default: compare with last commit
    try:
        result = subprocess.run(
            ["git", "show", "HEAD~1:.github/scripts/listings.json"],
            capture_output=True,
            text=True,
            check=True,
        )
        old_listings = json.loads(result.stdout)
    except subprocess.CalledProcessError:
        print("❌ Could not retrieve previous listings. Are you in a git repository?")
        return
    except json.JSONDecodeError:
        print("❌ Could not parse previous listings.")
        return

    # Compare listings
    old_urls = {listing["url"] for listing in old_listings}
    new_urls = {listing["url"] for listing in listings}

    added_urls = new_urls - old_urls
    removed_urls = old_urls - new_urls

    # Find status changes
    old_by_url = {listing["url"]: listing for listing in old_listings}
    new_by_url = {listing["url"]: listing for listing in listings}

    status_changes = []
    for url in old_urls & new_urls:
        old = old_by_url[url]
        new = new_by_url[url]
        if old.get("active") != new.get("active"):
            status_changes.append(
                {
                    "listing": new,
                    "old_active": old.get("active"),
                    "new_active": new.get("active"),
                }
            )

    print("Changes from previous commit")
    print("=" * 60)

    if added_urls:
        print(f"\n➕ ADDED ({len(added_urls)}):")
        for url in list(added_urls)[:20]:
            listing = new_by_url[url]
            print(f"  - {listing['company_name']}: {listing['title']}")

    if removed_urls:
        print(f"\n➖ REMOVED ({len(removed_urls)}):")
        for url in list(removed_urls)[:20]:
            listing = old_by_url[url]
            print(f"  - {listing['company_name']}: {listing['title']}")

    if status_changes:
        print(f"\n🔄 STATUS CHANGES ({len(status_changes)}):")
        for change in status_changes[:20]:
            listing = change["listing"]  # type: ignore
            old_status = "active" if change["old_active"] else "inactive"
            new_status = "active" if change["new_active"] else "inactive"
            print(f"  - {listing['company_name']}: {listing['title']} ({old_status} → {new_status})")

    if not added_urls and not removed_urls and not status_changes:
        print("\nNo changes from previous commit.")

    print(f"\nTotal: +{len(added_urls)} added, -{len(removed_urls)} removed, ~{len(status_changes)} status changes")


# =============================================================================
# Fix Command (Interactive)
# =============================================================================


def is_simplify_preferred(listing: Listing) -> bool:
    """Check if a listing is from Simplify with a company URL (preferred source).

    Args:
        listing: The listing to check.

    Returns:
        True if this is a preferred Simplify-sourced listing.
    """
    return listing.get("source") == "Simplify" and bool(listing.get("company_url", "").strip())


def _get_source_label(listing: Listing) -> str:
    """Get a label indicating the source of a listing."""
    if is_simplify_preferred(listing):
        return "[Simplify]"
    return f"[{listing.get('source', 'Unknown')}]"


def _format_listing_summary(listing: Listing) -> str:
    """Format a one-line summary of a listing."""
    company = listing.get("company_name", "Unknown")
    title = listing.get("title", "Unknown")
    date = datetime.fromtimestamp(listing.get("date_posted", 0)).strftime("%Y-%m-%d")
    return f"{company} - {title} (posted {date})"


def _scan_issues(listings: list[Listing]) -> list[dict[str, Any]]:
    """Scan listings for all fixable issues.

    Returns a list of issue dicts with type, listing(s), and details.
    """
    issues: list[dict[str, Any]] = []
    valid_categories = set(CATEGORIES.keys()) | {cat["name"] for cat in CATEGORIES.values()} | {"Other"}
    blocked_urls_lower = {url.lower() for url in BLOCKED_COMPANIES}

    # Build indexes for duplicate detection
    url_to_listings: dict[str, list[Listing]] = {}
    id_to_listings: dict[str, list[Listing]] = {}

    for listing in listings:
        url = listing.get("url", "")
        listing_id = listing.get("id", "")

        if url:
            url_to_listings.setdefault(url, []).append(listing)
        if listing_id:
            id_to_listings.setdefault(listing_id, []).append(listing)

    # Check for duplicate URLs
    for url, dupes in url_to_listings.items():
        if len(dupes) > 1:
            issues.append(
                {
                    "type": "duplicate_url",
                    "url": url,
                    "listings": dupes,
                }
            )

    # Check for duplicate IDs
    for listing_id, dupes in id_to_listings.items():
        if len(dupes) > 1:
            # Skip if already covered by duplicate URL
            if not any(i["type"] == "duplicate_url" and dupes[0] in i["listings"] for i in issues):
                issues.append(
                    {
                        "type": "duplicate_id",
                        "id": listing_id,
                        "listings": dupes,
                    }
                )

    # Check individual listings
    for listing in listings:
        # Empty title
        if not listing.get("title", "").strip():
            issues.append(
                {
                    "type": "empty_title",
                    "listing": listing,
                }
            )

        # Missing/None category
        category = listing.get("category")
        if category is None or category == "None" or (category and category not in valid_categories):
            issues.append(
                {
                    "type": "invalid_category",
                    "listing": listing,
                    "category": category,
                }
            )

        # Blocked company
        company_url = listing.get("company_url", "").lower()
        if any(blocked_url in company_url for blocked_url in blocked_urls_lower):
            issues.append(
                {
                    "type": "blocked_company",
                    "listing": listing,
                }
            )

    return issues


def cmd_listings_fix(dry_run: bool = False, issue_type: str | None = None, auto: bool = False) -> None:
    """Interactively fix issues in listings.json.

    Args:
        dry_run: If True, show what would be fixed without saving.
        issue_type: Only fix specific issue type (empty, duplicate, blocked).
        auto: If True, automatically accept all recommended fixes without prompting.
    """
    listings = get_listings_from_json()
    issues = _scan_issues(listings)

    # Filter by issue type if specified
    if issue_type:
        type_map = {
            "empty": ["empty_title", "invalid_category"],
            "duplicate": ["duplicate_url", "duplicate_id"],
            "blocked": ["blocked_company"],
        }
        allowed_types = type_map.get(issue_type, [issue_type])
        issues = [i for i in issues if i["type"] in allowed_types]

    if not issues:
        print("✅ No issues found!")
        return

    print(f"Found {len(issues)} issues to review")
    if dry_run:
        print("(DRY RUN - no changes will be saved)")
    if auto:
        print("(AUTO MODE - accepting all recommended fixes)")
    print("=" * 60)

    fixed_count = 0
    skipped_count = 0
    deleted_count = 0
    hidden_count = 0
    to_delete: set[str] = set()  # IDs to delete
    to_hide: set[str] = set()  # IDs to hide

    for i, issue in enumerate(issues, 1):
        issue_type_name = issue["type"]
        print(f"\nIssue {i}/{len(issues)}: {issue_type_name.replace('_', ' ').title()}")
        print("-" * 40)

        if issue_type_name == "empty_title":
            listing = issue["listing"]
            category = listing.get("category", "")
            print(f"Company: {listing.get('company_name', 'Unknown')}")
            print(f"Category: {category or 'None'}")
            print(f"ID: {listing.get('id', 'unknown')}")
            print(f"URL: {listing.get('url', 'N/A')}")
            print(f"Posted: {datetime.fromtimestamp(listing.get('date_posted', 0)).strftime('%Y-%m-%d')}")
            print()

            # Generate suggested title from category
            suggested_title = None
            if category and category not in ("None", "Other", None):
                suggested_title = f"{category} Intern"
            elif category == "Other":
                suggested_title = "Intern"

            if auto:
                if suggested_title:
                    if not dry_run:
                        listing["title"] = suggested_title
                    print(f'→ Auto: Set title to "{suggested_title}"')
                    fixed_count += 1
                else:
                    # No category to generate from, hide instead
                    if not dry_run:
                        to_hide.add(listing.get("id"))
                    print("→ Auto: Will hide (no category to generate title)")
                    hidden_count += 1
                continue

            # Show suggested title if available
            if suggested_title:
                print(f"Suggested title: {suggested_title}")
                choice = input("[a]ccept suggestion  [f]ix custom  [h]ide  [d]elete  [s]kip  [q]uit: ").strip().lower()
            else:
                choice = input("[f]ix  [h]ide  [d]elete  [s]kip  [q]uit: ").strip().lower()

            if choice == "a" and suggested_title:
                if not dry_run:
                    listing["title"] = suggested_title
                print(f'→ Fixed: Set title to "{suggested_title}"')
                fixed_count += 1
            elif choice == "f":
                new_title = input("Enter title: ").strip()
                if new_title:
                    if not dry_run:
                        listing["title"] = new_title
                    print(f'→ Fixed: Set title to "{new_title}"')
                    fixed_count += 1
                else:
                    print("→ Skipped (empty input)")
                    skipped_count += 1
            elif choice == "h":
                if not dry_run:
                    to_hide.add(listing.get("id"))
                print("→ Will hide from README")
                hidden_count += 1
            elif choice == "d":
                if not dry_run:
                    to_delete.add(listing.get("id"))
                print("→ Will delete")
                deleted_count += 1
            elif choice == "q":
                print("\nQuitting...")
                break
            else:
                print("→ Skipped")
                skipped_count += 1

        elif issue_type_name == "invalid_category":
            listing = issue["listing"]
            title = listing.get("title", "Unknown")
            current_cat = issue.get("category", "None")
            print(f"Company: {listing.get('company_name', 'Unknown')}")
            print(f"Title: {title}")
            print(f"Current category: {current_cat}")
            print(f"ID: {listing.get('id', 'unknown')}")
            print()

            # Try to suggest a category based on title
            suggested = classify_job_category(listing)

            # Auto mode: accept suggested category or default to "Other"
            if auto:
                selected_cat = suggested if suggested else "Other"
                if not dry_run:
                    listing["category"] = selected_cat
                print(f'→ Auto: Set category to "{selected_cat}"')
                fixed_count += 1
                continue

            # Show category options
            category_options = [
                "Software Engineering",
                "Product Management",
                "Data Science, AI & Machine Learning",
                "Quantitative Finance",
                "Hardware Engineering",
                "Other",
            ]

            print("Select category:")
            recommended_idx = None
            for idx, cat in enumerate(category_options, 1):
                if suggested and cat == suggested:
                    print(f"  [{idx}] {cat} <- RECOMMENDED (based on title)")
                    recommended_idx = idx
                else:
                    print(f"  [{idx}] {cat}")
            print()

            prompt = "Enter number (1-6)"
            if recommended_idx:
                prompt += f", [r] for recommended ({recommended_idx})"
            prompt += ", [s]kip, or [q]uit: "
            choice = input(prompt).strip().lower()

            if choice == "r" and recommended_idx:
                choice = str(recommended_idx)

            if choice.isdigit() and 1 <= int(choice) <= len(category_options):
                selected_cat = category_options[int(choice) - 1]
                if not dry_run:
                    listing["category"] = selected_cat
                print(f'→ Fixed: Set category to "{selected_cat}"')
                fixed_count += 1
            elif choice == "q":
                print("\nQuitting...")
                break
            else:
                print("→ Skipped")
                skipped_count += 1

        elif issue_type_name in ("duplicate_url", "duplicate_id"):
            dupes = issue["listings"]
            key = "URL" if issue_type_name == "duplicate_url" else "ID"
            value = issue.get("url") or issue.get("id")
            print(f"{key}: {value}")
            print()

            # Sort: Simplify preferred first, then by date_posted descending
            sorted_dupes = sorted(
                dupes,
                key=lambda x: (not is_simplify_preferred(x), -x.get("date_posted", 0)),
            )

            for j, dupe in enumerate(sorted_dupes, 1):
                label = _get_source_label(dupe)
                summary = _format_listing_summary(dupe)
                recommended = " <- RECOMMENDED" if j == 1 else ""
                print(f"  {j}. {label} {summary}{recommended}")

            # Auto mode: keep the first (Simplify preferred or newest)
            if auto:
                keep_idx = 0
                for j, dupe in enumerate(sorted_dupes):
                    if j != keep_idx:
                        if not dry_run:
                            to_delete.add(dupe.get("id"))
                        deleted_count += 1
                kept = sorted_dupes[keep_idx]
                print(f"→ Auto: Keeping {_get_source_label(kept)} {_format_listing_summary(kept)}")
                print(f"→ Deleting {len(sorted_dupes) - 1} duplicate(s)")
                fixed_count += 1
                continue

            print()
            options = " ".join([f"[{j}] keep #{j}" for j in range(1, len(sorted_dupes) + 1)])
            choice = input(f"{options}  [s]kip  [q]uit: ").strip().lower()

            if choice == "q":
                print("\nQuitting...")
                break
            elif choice.isdigit() and 1 <= int(choice) <= len(sorted_dupes):
                keep_idx = int(choice) - 1
                for j, dupe in enumerate(sorted_dupes):
                    if j != keep_idx:
                        if not dry_run:
                            to_delete.add(dupe.get("id"))
                        deleted_count += 1
                kept = sorted_dupes[keep_idx]
                print(f"→ Keeping: {_get_source_label(kept)} {_format_listing_summary(kept)}")
                print(f"→ Deleting {len(sorted_dupes) - 1} duplicate(s)")
                fixed_count += 1
            else:
                print("→ Skipped")
                skipped_count += 1

        elif issue_type_name == "blocked_company":
            listing = issue["listing"]
            print(f"Company: {listing.get('company_name', 'Unknown')}")
            print(f"Title: {listing.get('title', 'Unknown')}")
            print(f"Company URL: {listing.get('company_url', 'N/A')}")
            print(f"ID: {listing.get('id', 'unknown')}")
            print()

            # Auto mode: hide blocked companies
            if auto:
                if not dry_run:
                    to_hide.add(listing.get("id"))
                print("→ Auto: Will hide from README")
                hidden_count += 1
                continue

            choice = input("[h]ide  [d]elete  [s]kip  [q]uit: ").strip().lower()

            if choice == "h":
                if not dry_run:
                    to_hide.add(listing.get("id"))
                print("→ Will hide from README")
                hidden_count += 1
            elif choice == "d":
                if not dry_run:
                    to_delete.add(listing.get("id"))
                print("→ Will delete")
                deleted_count += 1
            elif choice == "q":
                print("\nQuitting...")
                break
            else:
                print("→ Skipped")
                skipped_count += 1

    # Apply changes
    if not dry_run and (to_delete or to_hide or fixed_count > 0):
        # Apply hide
        for listing in listings:
            if listing.get("id") in to_hide:
                listing["is_visible"] = False

        # Apply delete
        listings = [listing for listing in listings if listing.get("id") not in to_delete]

        # Save
        with open(LISTINGS_JSON_PATH, "w") as f:
            json.dump(listings, f, indent=4)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Fixed: {fixed_count}")
    print(f"Hidden: {hidden_count}")
    print(f"Deleted: {deleted_count}")
    print(f"Skipped: {skipped_count}")

    if dry_run:
        print("\n(DRY RUN - no changes were saved)")
    elif to_delete or to_hide or fixed_count > 0:
        print(f"\n✅ Changes saved to {LISTINGS_JSON_PATH}")
