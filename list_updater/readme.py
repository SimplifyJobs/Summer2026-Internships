"""README generation and embedding functions."""

from typing import Any

from list_updater.category import create_category_table, ensure_categories
from list_updater.constants import CATEGORIES, GITHUB_FILE_SIZE_LIMIT, SIZE_BUFFER
from list_updater.listings import filter_active, mark_stale_listings

type Listing = dict[str, Any]


def check_and_insert_warning(content: str, repo_name: str = "Summer2026-Internships") -> str:
    """Insert warning notice before GitHub cutoff point while preserving full content.

    Args:
        content: The README content.
        repo_name: The repository name for links.

    Returns:
        Content with warning inserted if necessary.
    """
    content_size = len(content.encode("utf-8"))

    if content_size <= (GITHUB_FILE_SIZE_LIMIT - SIZE_BUFFER):
        return content

    # Find insertion point well before the GitHub cutoff to warn users early
    target_size = GITHUB_FILE_SIZE_LIMIT - (2 * SIZE_BUFFER)

    # Convert to bytes for accurate measurement
    content_bytes = content.encode("utf-8")

    # Find the last complete table row before the limit
    insertion_bytes = content_bytes[:target_size]
    insertion_content = insertion_bytes.decode("utf-8", errors="ignore")

    # Find the last complete </tr> tag to ensure clean insertion
    last_tr_end = insertion_content.rfind("</tr>")
    if last_tr_end != -1:
        # Find the end of this row
        next_tr_start = insertion_content.find("\n", last_tr_end)
        if next_tr_start != -1:
            insertion_point = next_tr_start
        else:
            insertion_point = last_tr_end + 5  # After </tr>
    else:
        insertion_point = len(insertion_content)

    # Create the warning notice with anchor link
    full_list_url = "https://github.com/SimplifyJobs/Summer2026-Internships/blob/dev/README.md#-see-full-list"
    simplify_jobs_url = (
        "https://simplify.jobs/jobs?category=Software%20Engineering%3BHardware%20Engineering"
        "%3BQuantitative%20Finance%3BProduct%20Management%3BData%20%26%20Analytics%3BIT%20%26%20Security"
        "&jobId=2ac81173-86b5-4dbd-a7a9-260847c259cc&jobType=Internship?utm_source=GHList"
    )
    warning_notice = f"""
</tbody>
</table>

---

<div align="center" id="github-cutoff-warning">
  <h2>🔗 See Full List</h2>
  <p><strong>⚠️ GitHub preview cuts off around here due to file size limits.</strong></p>
  <p>📋 <strong><a href="{full_list_url}">Click here to view the complete list!</a></strong> 📋</p>
  <p><em>To find even more internships in tech, check out <a href="{simplify_jobs_url}">Simplify's website</a>.</em></p>
</div>

---

<table>
<thead>
<tr>
<th>Company</th>
<th>Role</th>
<th>Location</th>
<th>Application</th>
<th>Age</th>
</tr>
</thead>
<tbody>
"""

    # Split content at insertion point and insert warning
    before_insertion = content[:insertion_point]
    after_insertion = content[insertion_point:]

    return before_insertion + warning_notice + after_insertion


def embed_table(listings: list[Listing], filepath: str, off_season: bool = False) -> None:
    """Embed the listings table into a README file.

    Args:
        listings: List of listing dictionaries.
        filepath: Path to the README file to modify.
        off_season: Whether this is for off-season listings.
    """
    # Ensure all listings have a category
    listings = ensure_categories(listings)
    listings = mark_stale_listings(listings)

    # Filter only active listings
    active_listings = filter_active(listings)
    total_active = len(active_listings)

    # Count listings by category
    category_counts: dict[str, int] = {}
    for category_info in CATEGORIES.values():
        count = len([listing for listing in active_listings if listing["category"] == category_info["name"]])
        category_counts[category_info["name"]] = count

    # Build the category summary for the Browse section
    category_order = ["Software", "Product", "AI/ML/Data", "Quant", "Hardware"]
    category_links = []

    # Use the appropriate README file based on whether this is off-season or not
    readme_filename = "README-Off-Season.md" if off_season else "README.md"
    github_readme_base = f"https://github.com/SimplifyJobs/Summer2026-Internships/blob/dev/{readme_filename}"

    for category_key in category_order:
        if category_key in CATEGORIES:
            category_info = CATEGORIES[category_key]
            name = category_info["name"]
            emoji = category_info["emoji"]
            count = category_counts[name]
            anchor = name.lower().replace(" ", "-").replace(",", "").replace("&", "")
            category_links.append(f"{emoji} **[{name}]({github_readme_base}#-{anchor}-internship-roles)** ({count})")

    category_counts_str = "\n\n".join(category_links)

    new_text = ""
    in_browse_section = False
    browse_section_replaced = False
    in_table_section = False

    with open(filepath) as f:
        for line in f.readlines():
            if not browse_section_replaced and line.startswith("### Browse"):
                in_browse_section = True
                new_text += f"### Browse {total_active} Internship Roles by Category\n\n{category_counts_str}\n\n---\n"
                browse_section_replaced = True
                continue

            if in_browse_section:
                if line.startswith("---"):
                    in_browse_section = False
                continue

            if not in_table_section and "TABLE_START" in line:
                in_table_section = True
                new_text += line
                new_text += "\n---\n\n"

                # Add tables for each category in order
                for category_key in category_order:
                    if category_key in CATEGORIES:
                        category_info = CATEGORIES[category_key]
                        table = create_category_table(listings, category_info["name"], off_season)
                        if table:
                            new_text += table
                continue

            if in_table_section:
                if "TABLE_END" in line:
                    in_table_section = False
                    new_text += line
                continue

            if not in_browse_section and not in_table_section:
                new_text += line

    # Check content size and insert warning if necessary
    final_content = check_and_insert_warning(new_text)

    with open(filepath, "w") as f:
        f.write(final_content)
