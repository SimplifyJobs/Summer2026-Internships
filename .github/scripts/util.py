import re
import json
import os
from datetime import datetime
import time

# Set the TZ environment variable to PST
os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

# SIMPLIFY_BUTTON = "https://i.imgur.com/kvraaHg.png"
SIMPLIFY_BUTTON = "https://i.imgur.com/MXdpmi0.png" # says apply
SHORT_APPLY_BUTTON = "https://i.imgur.com/fbjwDvo.png"
SQUARE_SIMPLIFY_BUTTON = "https://i.imgur.com/aVnQdox.png"
LONG_APPLY_BUTTON = "https://i.imgur.com/6cFAMUo.png"
NON_SIMPLIFY_INACTIVE_THRESHOLD_MONTHS = 4
SIMPLIFY_INACTIVE_THRESHOLD_MONTHS = 8

CATEGORIES = {
    "Software": {"name": "Software Engineering", "emoji": "💻"},
    "AI/ML/Data": {"name": "Data Science, AI & Machine Learning", "emoji": "🤖"},
    "Quant": {"name": "Quantitative Finance", "emoji": "📈"},
    "Hardware": {"name": "Hardware Engineering", "emoji": "🔧"}
}

def setOutput(key, value):
    if output := os.getenv('GITHUB_OUTPUT', None):
        with open(output, 'a') as fh:
            print(f'{key}={value}', file=fh)

def fail(why):
    setOutput("error_message", why)
    exit(1)

def getLocations(listing):
    locations = "</br>".join(listing["locations"])
    if len(listing["locations"]) <= 3:
        return locations
    num = str(len(listing["locations"])) + " locations"
    return f'<details><summary>**{num}**</summary>{locations}</details>'

def getSponsorship(listing):
    if listing["sponsorship"] == "Does Not Offer Sponsorship":
        return " 🛂"
    elif listing["sponsorship"] == "U.S. Citizenship is Required":
        return " 🇺🇸"
    return ""

def getLink(listing):
    if not listing["active"]:
        return "🔒"
    link = listing["url"] 
    if "?" not in link:
        link += "?utm_source=Simplify&ref=Simplify"
    else:
        link += "&utm_source=Simplify&ref=Simplify"
    # return f'<a href="{link}" style="display: inline-block;"><img src="{SHORT_APPLY_BUTTON}" width="160" alt="Apply"></a>'

    if listing["source"] != "Simplify":
        return (
            f'<div align="center">'
            f'<a href="{link}"><img src="{LONG_APPLY_BUTTON}" width="88" alt="Apply"></a>'
            f'</div>'
        )

    simplifyLink = f"https://simplify.jobs/p/{listing['id']}?utm_source=GHList"
    return (
        f'<div align="center">'
        f'<a href="{link}"><img src="{SHORT_APPLY_BUTTON}" width="52" alt="Apply"></a> '
        f'<a href="{simplifyLink}"><img src="{SQUARE_SIMPLIFY_BUTTON}" width="28" alt="Simplify"></a>'
        f'</div>'
    )
    
def mark_stale_listings(listings):
    now = datetime.now()
    for listing in listings:
        age_in_months = (now - datetime.fromtimestamp(listing["date_posted"])).days / 30
        if listing["source"] != "Simplify" and age_in_months >= NON_SIMPLIFY_INACTIVE_THRESHOLD_MONTHS:
                listing["active"] = False
        elif listing["source"] == "Simplify" and age_in_months >= SIMPLIFY_INACTIVE_THRESHOLD_MONTHS:
            listing["active"] = False
    return listings

def filter_active(listings):
    return [listing for listing in listings if listing.get("active", False)]

def create_md_table(listings, offSeason=False):
    table = ""
    if offSeason:
        table += "| Company | Role | Location | Terms | Application | Age |\n"
        table += "| ------- | ---- | -------- | ----- | ------ | -- |\n"
    else:
        table += "| Company | Role | Location | Application | Age |\n"
        table += "| ------- | ---- | -------- | ------ | -- |\n"

    prev_company = None
    prev_days_active = None  # FIXED: previously incorrectly using date_posted

    for listing in listings:
        raw_url = listing.get("company_url", "").strip()
        company_url = raw_url + '?utm_source=GHList&utm_medium=company' if raw_url.startswith("http") else ""
        company = f"**[{listing['company_name']}]({company_url})**" if company_url else listing["company_name"]
        location = getLocations(listing)
        position = listing["title"] + getSponsorship(listing)
        terms = ", ".join(listing["terms"])
        link = getLink(listing)

        # calculate days active
        days_active = (datetime.now() - datetime.fromtimestamp(listing["date_posted"])).days
        days_active = max(days_active, 0)  # in case somehow negative
        days_display = (
            "0d" if days_active == 0 else
            f"{(days_active // 30)}mo" if days_active > 30 else
            f"{days_active}d"
        )
            
        # FIXED: comparison to see if same company and same days active
        if prev_company == listing['company_name'] and prev_days_active == days_active:
            company = "↳"
        else:
            prev_company = listing['company_name']
            prev_days_active = days_active
        
        if offSeason:
            table += f"| {company} | {position} | {location} | {terms} | {link} | {days_display} |\n"
        else:
            table += f"| {company} | {position} | {location} | {link} | {days_display} |\n"

    return table



def getListingsFromJSON(filename=".github/scripts/listings.json"):
    with open(filename) as f:
        listings = json.load(f)
        print(f"Received {len(listings)} listings from listings.json")
        return listings


def classifyJobCategory(job):
    # First check if there's an existing category
    if "category" in job and job["category"]:
        # Map the existing category to our standardized categories
        category = job["category"].lower()
        if category in ["hardware", "hardware engineering", "embedded engineering"]:
            return "Hardware Engineering"
        elif category in ["quant", "quantitative finance"]:
            return "Quantitative Finance"
        elif category in ["ai/ml/data", "data & analytics", "ai & machine learning", "data science"]:
            return "Data Science, AI & Machine Learning"
        elif category in ["software", "software engineering"]:
            return "Software Engineering"
    
    # If no category exists or it's not recognized, classify by title
    title = job.get("title", "").lower()
    if any(term in title for term in ["hardware", "embedded", "fpga", "circuit", "chip", "silicon", "asic"]):
        return "Hardware Engineering"
    elif any(term in title for term in ["quant", "quantitative", "trading", "finance", "investment"]):
        return "Quantitative Finance"
    elif any(term in title for term in ["data science", "data engineer", "data scientist", "data engineering", "ai &", "machine learning", "ml", "analytics", "analyst" ]):
        return "Data Science, AI & Machine Learning"
    return "Software Engineering"

def ensureCategories(listings):
    for listing in listings:
        listing["category"] = classifyJobCategory(listing)
    return listings

def create_category_table(listings, category_name):
    category_listings = [l for l in listings if l["category"] == category_name]
    if not category_listings:
        return ""

    emoji = next((cat["emoji"] for cat in CATEGORIES.values() if cat["name"] == category_name), "")
    header = f"\n\n## {emoji} {category_name} Internship Roles\n\n"
    header += "[Back to top](#summer-2025-tech-internships-by-pitt-csc--simplify)\n\n"

    # Optional callout under Data Science section
    if category_name == "Data Science, AI & Machine Learning":
        header += (
            "> 🎓 Here's the [resume template](https://docs.google.com/document/d/1azvJt51U2CbpvyO0ZkICqYFDhzdfGxU_lsPQTGhsn94/edit?usp=sharing) used by Stanford CS and Pitt CSC for internship prep.\n"
            "\n"
            "> 🧠 Want to know what keywords your resume is missing for a job? Use the blue Simplify application link to instantly compare your resume to any job description.\n\n"
        )

    # Sort and format
    active = sorted([l for l in category_listings if l["active"]], key=lambda l: l["date_posted"], reverse=True)
    inactive = sorted([l for l in category_listings if not l["active"]], key=lambda l: l["date_posted"], reverse=True)

    result = header
    if active:
        result += create_md_table(active) + "\n\n"

    if inactive:
        result += (
            "<details>\n"
            f"<summary>🗃️ Inactive roles ({len(inactive)})</summary>\n\n"
            + create_md_table(inactive) +
            "\n\n</details>\n\n"
        )

    return result

def embedTable(listings, filepath, offSeason=False):
    # Ensure all listings have a category
    listings = ensureCategories(listings)
    listings = mark_stale_listings(listings)
    # Filter only active listings
    active_listings = filter_active(listings)
    total_active = len(active_listings)

    # Count listings by category
    category_counts = {}
    for category_info in CATEGORIES.values():
        count = len([l for l in active_listings if l["category"] == category_info["name"]])
        category_counts[category_info["name"]] = count

    # Build the category summary for the Browse section
    category_links = []
    for category_info in CATEGORIES.values():
        name = category_info["name"]
        emoji = category_info["emoji"]
        anchor = name.lower().replace(" ", "-").replace(",", "").replace("&", "")
        category_links.append(f"{emoji} **[{name}](#-{anchor}-internship-roles)** ({category_counts[name]})")
    category_counts_str = "\n\n".join(category_links)

    newText = ""
    in_browse_section = False
    browse_section_replaced = False
    in_table_section = False
    table_section_replaced = False

    with open(filepath, "r") as f:
        for line in f.readlines():
            if not browse_section_replaced and line.startswith("### Browse"):
                in_browse_section = True
                newText += f"### Browse {total_active} Internship Roles by Category\n\n{category_counts_str}\n\n---\n"
                browse_section_replaced = True
                continue

            if in_browse_section:
                if line.startswith("---"):
                    in_browse_section = False
                continue

            if not in_table_section and "TABLE_START" in line:
                in_table_section = True
                newText += line
                newText += "\n---\n\n"
                for category_info in CATEGORIES.values():
                    name = category_info["name"]
                    table = create_category_table(listings, name)
                    if table:
                        newText += table
                continue

            if in_table_section:
                if "TABLE_END" in line:
                    in_table_section = False
                    newText += line
                continue

            if not in_browse_section and not in_table_section:
                newText += line

    with open(filepath, "w") as f:
        f.write(newText)


def filterSummer(listings, year, earliest_date):
    return [listing for listing in listings if listing["is_visible"] and any(f"Summer {year}" in item for item in listing["terms"]) and listing['date_posted'] > earliest_date]


def filterOffSeason(listings):
    def isOffSeason(listing):
        if not listing.get("is_visible"):
            return False
        
        terms = listing.get("terms", [])
        has_off_season_term = any(season in term for term in terms for season in ["Fall", "Winter", "Spring"])
        has_summer_term = any("Summer" in term for term in terms)

        # We don't want to include listings in the off season list if they include a Summer term
        #
        # Due to the nature of classification, there will sometimes be edge cases where an internship might
        # be included in two different seasons (e.g. Summer + Fall). More often than not though, these types of listings
        # are targeted towards people looking for summer internships.
        #
        # We can re-visit this in the future, but excluding listings with "Summer" term for better UX for now.
        return has_off_season_term and not has_summer_term

    return [listing for listing in listings if isOffSeason(listing)]


def sortListings(listings):
    oldestListingFromCompany = {}
    linkForCompany = {}

    for listing in listings:
        date_posted = listing["date_posted"]
        if listing["company_name"].lower() not in oldestListingFromCompany or oldestListingFromCompany[listing["company_name"].lower()] > date_posted:
            oldestListingFromCompany[listing["company_name"].lower()] = date_posted
        if listing["company_name"] not in linkForCompany or len(listing["company_url"]) > 0:
            linkForCompany[listing["company_name"]] = listing["company_url"]

    listings.sort(
        key=lambda x: (
            x["active"],  # Active listings first
            x['date_posted'],
            x['company_name'].lower(),
            x['date_updated']
        ),
        reverse=True
    )

    for listing in listings:
        listing["company_url"] = linkForCompany[listing["company_name"]]

    return listings


def checkSchema(listings):
    props = ["source", "company_name",
             "id", "title", "active", "date_updated", "is_visible",
             "date_posted", "url", "locations", "company_url", "terms",
             "sponsorship"]
    for listing in listings:
        for prop in props:
            if prop not in listing:
                fail("ERROR: Schema check FAILED - object with id " +
                      listing["id"] + " does not contain prop '" + prop + "'")