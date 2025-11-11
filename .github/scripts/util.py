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
NON_SIMPLIFY_INACTIVE_THRESHOLD_MONTHS = 2
SIMPLIFY_INACTIVE_THRESHOLD_MONTHS = 2

# Set of Simplify company URLs to block from appearing in the README
# Add Simplify company URLs to block them (e.g., "https://simplify.jobs/c/Jerry")
BLOCKED_COMPANIES = {
    "https://simplify.jobs/c/Jerry",
}

# FAANG+ companies - will be marked with fire emoji
FAANG_PLUS = {
    "airbnb", "adobe", "amazon", "amd", "anthropic", "apple", "asana", "atlassian", "bytedance", "cloudflare","coinbase", "crowdstrike","databricks", "datadog",
    "doordash", "dropbox", "duolingo", "figma", "google", "ibm", "instacart", "intel", "linkedin", "lyft", "meta", "microsoft",
    "netflix", "notion", "nvidia", "openai", "oracle", "palantir", "paypal", "perplexity", "pinterest", "ramp", "reddit","rippling", "robinhood", "roblox",
    "salesforce", "samsara", "servicenow", "shopify", "slack", "snap", "snapchat", "spacex", "splunk","snowflake", "stripe", "square", "tesla", "tinder","tiktok", "uber",
    "visa","waymo", "x"
}

CATEGORIES = {
    "Software": {"name": "Software Engineering", "emoji": "💻"},
    "Product": {"name": "Product Management", "emoji": "📱"},
    "AI/ML/Data": {"name": "Data Science, AI & Machine Learning", "emoji": "🤖"},
    "Quant": {"name": "Quantitative Finance", "emoji": "📈"},
    "Hardware": {"name": "Hardware Engineering", "emoji": "🔧"}
}

def setOutput(key, value):
    if output := os.getenv('GITHUB_OUTPUT', None):
        with open(output, 'a') as fh:
            # Use delimiter format for multiline values
            import uuid
            delimiter = f'ghadelimiter_{uuid.uuid4()}'
            # Convert value to string and handle multiline
            value_str = str(value)
            if '\n' in value_str or any(char in value_str for char in ['*', '#', '`', '[', ']']):
                # Use heredoc format for multiline or special character values
                print(f'{key}<<{delimiter}', file=fh)
                print(value_str, file=fh)
                print(delimiter, file=fh)
            else:
                # Simple format for single-line values
                print(f'{key}={value_str}', file=fh)

def fail(why):
    setOutput("error_message", why)
    exit(1)

def getLocations(listing):
    locations = "</br>".join(listing["locations"])
    if len(listing["locations"]) <= 3:
        return locations
    num = str(len(listing["locations"])) + " locations"
    return f'<details><summary><strong>{num}</strong></summary>{locations}</details>'

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

    if listing["source"] != "Simplify":
        # Non-Simplify jobs: single button, centered with smaller width to prevent wrapping
        return (
            f'<div align="center">'
            f'<a href="{link}"><img src="{LONG_APPLY_BUTTON}" width="80" alt="Apply"></a>'
            f'</div>'
        )

    # Simplify jobs: two buttons with smaller widths to prevent wrapping
    simplifyLink = f"https://simplify.jobs/p/{listing['id']}?utm_source=GHList"
    return (
        f'<div align="center">'
        f'<a href="{link}"><img src="{SHORT_APPLY_BUTTON}" width="50" alt="Apply"></a> '
        f'<a href="{simplifyLink}"><img src="{SQUARE_SIMPLIFY_BUTTON}" width="26" alt="Simplify"></a>'
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

def convert_markdown_to_html(text):
    """Convert markdown formatting to HTML for proper rendering in HTML table cells"""
    # Convert **bold** to <strong>bold</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Convert [link text](url) to <a href="url">link text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    return text

def get_minimal_css():
    """Return minimal CSS for basic table functionality"""
    return """
<!-- Minimal table styling for better readability -->
<style>
table { border-collapse: collapse; width: 100%; }
th { text-align: left; font-weight: bold; }
.td-center { text-align: center; }
</style>

"""

def create_md_table(listings, offSeason=False):
    # Create clean HTML table with minimal styling
    table = '<table>\n<thead>\n<tr>\n'
    
    if offSeason:
        table += '<th>Company</th>\n'
        table += '<th>Role</th>\n'
        table += '<th>Location</th>\n'
        table += '<th>Terms</th>\n'
        table += '<th>Application</th>\n'
        table += '<th>Age</th>\n'
    else:
        table += '<th>Company</th>\n'
        table += '<th>Role</th>\n'
        table += '<th>Location</th>\n'
        table += '<th>Application</th>\n'
        table += '<th>Age</th>\n'
    
    table += '</tr>\n</thead>\n<tbody>\n'

    prev_company = None
    prev_days_active = None  # FIXED: previously incorrectly using date_posted

    for listing in listings:
        # Check if this is a FAANG+ company for fire emoji
        company_name = listing["company_name"]
        is_faang_plus = company_name.lower() in FAANG_PLUS
        
        raw_url = listing.get("company_url", "").strip()
        company_url = raw_url + '?utm_source=GHList&utm_medium=company' if raw_url.startswith("http") else ""
        company_markdown = f"**[{company_name}]({company_url})**" if company_url else f"**{company_name}**"
        
        # Add fire emoji outside the link for FAANG+ companies
        if is_faang_plus:
            company_markdown = f"🔥 {company_markdown}"
        
        company = convert_markdown_to_html(company_markdown)
        location = getLocations(listing)
        
        # Check for advanced degree requirements and add graduation cap emoji
        title_with_degree_emoji = listing["title"]
        
        # Check degrees field for advanced degree requirements
        degrees = listing.get("degrees", [])
        if degrees:
            # Check if only advanced degrees are required (no Bachelor's or Associate's)
            has_bachelors_or_associates = any(
                degree.lower() in ["bachelor's", "associate's"]
                for degree in degrees
            )
            has_advanced_degrees = any(
                degree.lower() in ["master's", "phd", "mba"]
                for degree in degrees
            )
            
            if has_advanced_degrees and not has_bachelors_or_associates:
                title_with_degree_emoji += " 🎓"
        
        # Also check title text for degree mentions
        title_lower = listing["title"].lower()
        if any(term in title_lower for term in ["master's", "masters", "master", "mba", "phd", "ph.d", "doctorate", "doctoral"]):
            if "🎓" not in title_with_degree_emoji:
                title_with_degree_emoji += " 🎓"
        
        position = title_with_degree_emoji + getSponsorship(listing)
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
        if prev_company == company_name and prev_days_active == days_active:
            company = "↳"
        else:
            prev_company = company_name
            prev_days_active = days_active
        
        # Create HTML table row
        table += '<tr>\n'
        
        if offSeason:
            table += f'<td>{company}</td>\n'
            table += f'<td>{position}</td>\n'
            table += f'<td>{location}</td>\n'
            table += f'<td>{terms}</td>\n'
            table += f'<td>{link}</td>\n'
            table += f'<td>{days_display}</td>\n'
        else:
            table += f'<td>{company}</td>\n'
            table += f'<td>{position}</td>\n'
            table += f'<td>{location}</td>\n'
            table += f'<td>{link}</td>\n'
            table += f'<td>{days_display}</td>\n'
        
        table += '</tr>\n'

    table += '</tbody>\n</table>\n'
    return table



def getListingsFromJSON(filename=".github/scripts/listings.json"):
    with open(filename) as f:
        listings = json.load(f)
        print(f"Received {len(listings)} listings from listings.json")
        return listings


def classifyJobCategory(job):
    # Always classify by title for better accuracy, ignore existing category
    title = job.get("title", "").lower()
    
    # Filter out IT technical support roles that aren't really tech internships
    if any(term in title for term in [
        "it technical intern", "it technician", "it support", "technical support intern",
        "help desk", "desktop support", "it help desk", "computer support", "security operations", "field operations",
        "information technology"
    ]):
        return None
    
    # Hardware (first priority) - expanded keywords
    if any(term in title for term in [
        "hardware", "embedded", "fpga", "circuit", "chip", "silicon", "asic", "robotics", "firmware", 
        "manufactur", "electrical", "mechanical", "systems engineer", "test engineer", "validation",
        "verification", "pcb", "analog", "digital", "signal", "power", "rf", "antenna"
    ]):
        return "Hardware Engineering"
    
    # Quant (second priority) - expanded keywords
    elif any(term in title for term in [
        "quant", "quantitative", "trading", "finance", "investment", "financial", "risk", "portfolio",
        "derivatives", "algorithmic trading", "market", "capital", "equity", "fixed income", "credit"
    ]):
        return "Quantitative Finance"
    
    # Data Science (third priority) - expanded keywords
    elif any(term in title for term in [
        "data science", "artificial intelligence", "data scientist", "ai", "machine learning", "ml", 
        "data analytics", "data analyst", "research eng", "nlp", "computer vision", "research sci", 
        "data eng", "analytics", "statistician", "modeling", "algorithms", "deep learning", "pytorch",
        "tensorflow", "pandas", "numpy", "sql", "etl", "pipeline", "big data", "spark", "hadoop"
    ]):
        return "Data Science, AI & Machine Learning"
    
    # Product (fourth priority) - check before Software to catch "Software Product Management" roles
    elif any(term in title for term in [
        "product manag", "product analyst", "apm", "associate product", "product owner", "product design",
        "product marketing", "product strategy", "business analyst", "program manag", "project manag"
    ]) or ("product" in title and any(word in title for word in ["analyst", "manager", "associate", "coordinator"])):
        return "Product Management"
    
    # Software Engineering (fifth priority) - greatly expanded keywords
    elif any(term in title for term in [
        "software", "engineer", "developer", "dev", "programming", "coding", "fullstack", "full-stack", 
        "full stack", "frontend", "front end", "front-end", "backend", "back end", "back-end", 
        "mobile", "web", "app", "application", "platform", "infrastructure", "cloud", "devops", 
        "sre", "site reliability", "systems", "network", "security", "cybersecurity", "qa", 
        "quality assurance", "test", "automation", "ci/cd", "deployment", "kubernetes", "docker",
        "aws", "azure", "gcp", "api", "microservices", "database", "java", "python", "javascript",
        "react", "node", "golang", "rust", "c++", "c#", ".net", "ios", "android", "flutter",
        "technical", "technology", "tech", "coding", "programming", "sde", "swe"
    ]):
        return "Software Engineering"
    
    # Return None for jobs that don't fit any category (will be filtered out)
    else:
        return "Software Engineering"

def ensureCategories(listings):
    categorized_listings = []
    filtered_count = 0
    
    # Create mapping from old category names to new category names
    category_mapping = {
        "Software": "Software Engineering",
        "Product": "Product Management", 
        "AI/ML/Data": "Data Science, AI & Machine Learning",
        "Quant": "Quantitative Finance",
        "Hardware": "Hardware Engineering"
    }
    
    for listing in listings:
        # If listing already has a category, normalize it to full category name
        if "category" in listing and listing["category"]:
            existing_category = listing["category"]
            # Normalize old category names to new full names
            if existing_category in category_mapping:
                listing["category"] = category_mapping[existing_category]
                categorized_listings.append(listing)
            # Re-classify jobs with "Other" or invalid categories
            elif existing_category in ["Other", "None", None]:
                category = classifyJobCategory(listing)
                if category is not None:
                    listing["category"] = category
                    categorized_listings.append(listing)
                else:
                    filtered_count += 1
            else:
                # Keep jobs with valid full category names
                categorized_listings.append(listing)
        else:
            # Only auto-classify if no category exists
            category = classifyJobCategory(listing)
            if category is not None:  # Only keep jobs that fit our categories
                listing["category"] = category
                categorized_listings.append(listing)
            else:
                filtered_count += 1
    
    print(f"Filtered out {filtered_count} jobs that didn't fit any category")
    return categorized_listings

def create_category_table(listings, category_name, offSeason=False):
    category_listings = [l for l in listings if l["category"] == category_name]
    if not category_listings:
        return ""

    emoji = next((cat["emoji"] for cat in CATEGORIES.values() if cat["name"] == category_name), "")
    header = f"\n\n## {emoji} {category_name} Internship Roles\n\n"
    header += "[Back to top](#summer-2026-tech-internships-by-pitt-csc--simplify)\n\n"

    # Optional callout under Data Science section
    if category_name == "Data Science, AI & Machine Learning":
        header += (
            "> 📄 Here's the [resume template](https://docs.google.com/document/d/1azvJt51U2CbpvyO0ZkICqYFDhzdfGxU_lsPQTGhsn94/edit?usp=sharing) used by Stanford CS and Pitt CSC for internship prep.\n"
            "\n"
            "> 🧠 Want to know what keywords your resume is missing for a job? Use the blue Simplify application link to instantly compare your resume to any job description.\n\n"
        )
        
    if category_name == 'Product Management':
        header += (
            "> 📅 Curious when Big Tech product internships typically open? Simplify put together an [openings tracker](https://simplify.jobs/top-list/Associate-Product-Manager-Intern?utm_source=GHList&utm_medium=ot) based on historical data for those companies.\n"
            "\n"
        )

    # Sort and format
    active = sorted([l for l in category_listings if l["active"]], key=lambda l: l["date_posted"], reverse=True)
    inactive = sorted([l for l in category_listings if not l["active"]], key=lambda l: l["date_posted"], reverse=True)

    result = header
    if active:
        result += create_md_table(active, offSeason) + "\n\n"

    if inactive:
        result += (
            "<details>\n"
            f"<summary>🗃️ Inactive roles ({len(inactive)})</summary>\n\n"
            + create_md_table(inactive, offSeason) +
            "\n\n</details>\n\n"
        )

    return result

# GitHub README file size limit (500 KiB = 512,000 bytes)
GITHUB_FILE_SIZE_LIMIT = 512000
# Smaller buffer to show warning closer to actual cutoff (5 KiB buffer)
SIZE_BUFFER = 5120

def check_and_insert_warning(content, repo_name="Summer2026-Internships"):
    """Insert warning notice before GitHub cutoff point while preserving full content"""
    content_size = len(content.encode('utf-8'))
    
    if content_size <= (GITHUB_FILE_SIZE_LIMIT - SIZE_BUFFER):
        return content
    
    # Find insertion point well before the GitHub cutoff to warn users early
    # This leaves ~200KB of content after the warning that GitHub will actually cut off
    target_size = GITHUB_FILE_SIZE_LIMIT - (2* SIZE_BUFFER)  # 500000 KB - very early warning to leave plenty of space for more internships
    
    # Convert to bytes for accurate measurement
    content_bytes = content.encode('utf-8')
    
    # Find the last complete table row before the limit
    insertion_bytes = content_bytes[:target_size]
    insertion_content = insertion_bytes.decode('utf-8', errors='ignore')
    
    # Find the last complete </tr> tag to ensure clean insertion
    last_tr_end = insertion_content.rfind('</tr>')
    if last_tr_end != -1:
        # Find the end of this row
        next_tr_start = insertion_content.find('\n', last_tr_end)
        if next_tr_start != -1:
            insertion_point = next_tr_start
        else:
            insertion_point = last_tr_end + 5  # After </tr>
    else:
        insertion_point = len(insertion_content)
    
    # Create the warning notice with anchor link
    warning_notice = f"""
</tbody>
</table>

---

<div align="center" id="github-cutoff-warning">
  <h2>🔗 See Full List</h2>
  <p><strong>⚠️ GitHub preview cuts off around here due to file size limits.</strong></p>
  <p>📋 <strong><a href="https://github.com/SimplifyJobs/Summer2026-Internships/blob/dev/README.md#-see-full-list">Click here to view the complete list with all internship opportunities!</a></strong> 📋</p>
  <p><em>To find even more internships in tech, check out <a href="https://simplify.jobs/jobs?category=Software%20Engineering%3BHardware%20Engineering%3BQuantitative%20Finance%3BProduct%20Management%3BData%20%26%20Analytics%3BIT%20%26%20Security&jobId=2ac81173-86b5-4dbd-a7a9-260847c259cc&jobType=Internship?utm_source=GHList">Simplify's website</a>.</em></p>
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
    # Order: Software, Product, Data, Quant, Hardware
    category_order = ["Software", "Product", "AI/ML/Data", "Quant", "Hardware"]
    category_links = []
    # Use the appropriate README file based on whether this is off-season or not
    readme_filename = "README-Off-Season.md" if offSeason else "README.md"
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
                # Add minimal CSS styles (optional - can be removed entirely)
                # newText += get_minimal_css()
                # Add tables for each category in order
                category_order = ["Software", "Product", "AI/ML/Data", "Quant", "Hardware"]
                for category_key in category_order:
                    if category_key in CATEGORIES:
                        category_info = CATEGORIES[category_key]
                        table = create_category_table(listings, category_info["name"], offSeason)
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

    # Check content size and insert warning if necessary
    final_content = check_and_insert_warning(newText)
    
    with open(filepath, "w") as f:
        f.write(final_content)


def filterSummer(listings, year, earliest_date):
    # Convert blocked URLs to lowercase for case-insensitive comparison
    blocked_urls_lower = {url.lower() for url in BLOCKED_COMPANIES}
    
    final_listings = []
    for listing in listings:
        if listing["is_visible"] and any(f"Summer {year}" in item for item in listing["terms"]) and listing['date_posted'] > earliest_date:
            # Check if listing is from a blocked company
            company_url = listing.get("company_url", "").lower()
            if not any(blocked_url in company_url for blocked_url in blocked_urls_lower):
                final_listings.append(listing)
    
    return final_listings


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