#!/usr/bin/env python3
"""List Updater CLI - Internship listing management tool."""

from pathlib import Path

import typer

from list_updater import (
    cmd_contribution_process,
    cmd_listings_diff,
    cmd_listings_fix,
    cmd_listings_mark_inactive,
    cmd_listings_search,
    cmd_listings_stats,
    cmd_listings_validate,
    cmd_readme_update,
)

app = typer.Typer(
    name="list-updater",
    help="Internship listing management CLI for GitHub Actions",
    no_args_is_help=True,
)

# =============================================================================
# README Commands
# =============================================================================

readme_app = typer.Typer(help="README operations")
app.add_typer(readme_app, name="readme")


@readme_app.command("update")
def readme_update() -> None:
    """Update README files from listings.json."""
    cmd_readme_update()


# =============================================================================
# Contribution Commands
# =============================================================================

contribution_app = typer.Typer(help="Contribution processing")
app.add_typer(contribution_app, name="contribution")


@contribution_app.command("process")
def contribution_process(
    event_file: Path = typer.Argument(..., help="Path to GitHub event JSON file"),
) -> None:
    """Process an approved contribution issue (new/edit internship)."""
    cmd_contribution_process(str(event_file))


# =============================================================================
# Listings Commands
# =============================================================================

listings_app = typer.Typer(help="Listings management and analytics")
app.add_typer(listings_app, name="listings")


@listings_app.command("mark-inactive")
def listings_mark_inactive(
    event_file: Path = typer.Argument(..., help="Path to GitHub event JSON file"),
) -> None:
    """Bulk mark listings as inactive from a GitHub issue."""
    cmd_listings_mark_inactive(str(event_file))


@listings_app.command("stats")
def listings_stats(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show listing statistics (counts, categories, top companies)."""
    cmd_listings_stats(json_output=json_output)


@listings_app.command("validate")
def listings_validate(
    fix: bool = typer.Option(False, "--fix", help="Attempt to auto-fix issues"),
) -> None:
    """Validate listings.json schema and data integrity."""
    cmd_listings_validate(fix=fix)


@listings_app.command("search")
def listings_search(
    company: str | None = typer.Option(None, "--company", "-c", help="Filter by company name"),
    title: str | None = typer.Option(None, "--title", "-t", help="Filter by job title"),
    location: str | None = typer.Option(None, "--location", "-l", help="Filter by location"),
    category: str | None = typer.Option(None, "--category", help="Filter by category"),
    active: bool = typer.Option(False, "--active", help="Show only active listings"),
    inactive: bool = typer.Option(False, "--inactive", help="Show only inactive listings"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results to show"),
) -> None:
    """Search and filter listings."""
    cmd_listings_search(
        company=company,
        title=title,
        location=location,
        category=category,
        active_only=active,
        inactive_only=inactive,
        limit=limit,
    )


@listings_app.command("diff")
def listings_diff(
    since: str | None = typer.Option(None, "--since", help="Show changes since date (YYYY-MM-DD)"),
    commit: str | None = typer.Option(None, "--commit", help="Show changes since git commit"),
) -> None:
    """Show changes to listings since a date or commit."""
    cmd_listings_diff(since=since, commit=commit)


@listings_app.command("fix")
def listings_fix(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show fixes without saving"),
    issue_type: str | None = typer.Option(None, "--type", help="Only fix specific type: empty, duplicate, blocked"),
    auto: bool = typer.Option(False, "--auto", help="Auto-accept all recommended fixes"),
) -> None:
    """Interactively fix issues in listings.json."""
    cmd_listings_fix(dry_run=dry_run, issue_type=issue_type, auto=auto)


if __name__ == "__main__":
    app()
