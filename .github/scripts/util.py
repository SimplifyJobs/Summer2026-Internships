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
        return f'<a href="{link}"><img src="{LONG_APPLY_BUTTON}" width="88" alt="Apply"></a>'
    
    simplifyLink = "https://simplify.jobs/p/" + listing["id"] + "?utm_source=GHList"
    return f'<a href="{link}"><img src="{SHORT_APPLY_BUTTON}" width="56" alt="Apply"></a> <a href="{simplifyLink}"><img src="{SQUARE_SIMPLIFY_BUTTON}" width="30" alt="Simplify"></a>'

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

def embedTable(listings, filepath, offSeason=False):
    newText = ""
    readingTable = False
    with open(filepath, "r") as f:
        for line in f.readlines():
            if readingTable:
                if "|" not in line and "TABLE_END" in line:
                    newText += line
                    readingTable = False
                continue
            else:
                newText += line
                if "TABLE_START" in line:
                    readingTable = True
                    newText += "\n" + create_md_table(listings, offSeason=offSeason) + "\n"
    
    # Calculate counts
    active_listings = [listing for listing in listings if listing.get("active", False)]
    total_active = len(active_listings)

    # Replace the "Browse ### Internship Roles by Category" section automatically
    browse_section_pattern = r"(### Browse )(.*?)( Internship Roles\s*-+\n)"
    newText = re.sub(browse_section_pattern, f"### Browse {total_active} Internship Roles\n\n---\n", newText, count=1, flags=re.DOTALL)

    # Write final output
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
