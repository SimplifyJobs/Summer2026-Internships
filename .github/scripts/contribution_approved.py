import json
import sys
import uuid
from datetime import datetime
from typing import Union, Optional
import util
import re

NO_ANSWER = {"", "no response", "_no response_", "none", "n/a", "na", "-"}
YES_VALUES = {"yes", "y", "true", "open"}
NO_VALUES  = {"no", "n", "false", "closed"}

CATEGORY_MAPPING = {
    "software engineering": "Software Engineering",
    "product management": "Product Management",
    "data science, ai & machine learning": "Data Science, AI & Machine Learning",
    "data science": "Data Science, AI & Machine Learning",
    "ai": "Data Science, AI & Machine Learning",
    "machine learning": "Data Science, AI & Machine Learning",
    "quantitative finance": "Quantitative Finance",
    "hardware engineering": "Hardware Engineering"
}

def _clean(s: str) -> str:
    return re.sub(r"[\s*_`]+", " ", s or "").strip()

def _is_no_answer(s: str) -> bool:
    return _clean(s).lower() in NO_ANSWER

def _norm_category(raw: str) -> Optional[str]:
    if _is_no_answer(raw):
        return None
    key = _clean(raw).lower()
    return CATEGORY_MAPPING.get(key)

def _parse_bool(raw: str) -> Optional[bool]:
    if _is_no_answer(raw):
        return None
    val = _clean(raw).lower()
    if val in YES_VALUES: return True
    if val in NO_VALUES:  return False
    return None

def add_https_to_url(url):
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url

def getData(body, is_edit, username):
    lines = [text.strip("# ").strip() for text in re.split(r'[\n\r]+', body)]
    data = {"date_updated": int(datetime.now().timestamp())}

    # Defaults for NEW only
    if not is_edit:
        data.update({
            "sponsorship": "Offers Sponsorship",
            "active": True,
            "degrees": ["Bachelor's"],
        })

    def next_line_value(idx) -> str:
        if idx + 1 >= len(lines):
            return ""
        next_line = lines[idx + 1].strip()
        # If the next line is another header (starts with a word followed by colon or question mark),
        # then this field was left empty in the YAML form
        if next_line and (next_line.endswith("?") or next_line.endswith(":")):
            return ""
        # If it's clearly a section header, treat as empty
        header_patterns = ["Company Name", "Internship Title", "Location", "What term", "Does this", 
                          "Is this", "Permanently remove", "What category", "Advanced Degree", 
                          "Email associated", "Extra Notes", "Reason for"]
        if any(pattern in next_line for pattern in header_patterns):
            return ""
        return next_line

    # Track which fields were explicitly provided in the form
    provided_fields = set()

    for i, line in enumerate(lines):
        # URL
        if "Link to Internship Posting" in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["url"] = add_https_to_url(v)
                provided_fields.add("url")

        # Company
        elif "Company Name" in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["company_name"] = _clean(v)
                provided_fields.add("company_name")

        # Title
        elif "Internship Title" in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["title"] = _clean(v)
                provided_fields.add("title")

        # Locations
        elif "Location" in line and "Email" not in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["locations"] = [ _clean(loc) for loc in v.split("|") if _clean(loc) ]
                provided_fields.add("locations")

        # Terms
        elif "What term(s) is this internship offered for?" in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["terms"] = [ _clean(term) for term in v.split(",") if _clean(term) ]
                provided_fields.add("terms")

        # Sponsorship
        elif "Does this internship offer sponsorship?" in line:
            v = next_line_value(i)
            if not _is_no_answer(v):
                data["sponsorship"] = "Other"
                for option in ["Offers Sponsorship", "Does Not Offer Sponsorship", "U.S. Citizenship is Required"]:
                    if option.lower() in v.lower():
                        data["sponsorship"] = option
                        break
                provided_fields.add("sponsorship")

        # Active (edit/new variants)
        elif ("Is this internship still accepting applications?" in line) or \
             ("Is this internship currently accepting applications?" in line):
            v = next_line_value(i)
            ans = _parse_bool(v)
            if ans is not None:
                data["active"] = ans
                provided_fields.add("active")
            elif not is_edit and "active" not in data:
                data["active"] = True
                provided_fields.add("active")

        # Category (defer mapping; we just capture candidate)
        elif "What category does this internship belong to?" in line:
            v = next_line_value(i)
            cat = _norm_category(v)
            if cat is not None:
                data["category"] = cat
                provided_fields.add("category")
            # If no valid category provided, let auto-classification handle it later

        # Advanced degree
        elif "Advanced Degree Requirements" in line:
            # look at the next line specifically (not multiple lines)
            checked = False
            provided = False
            if i + 1 < len(lines):
                val = lines[i + 1].strip().lower()
                # Only consider it provided if there's actual checkbox content
                if "[x]" in val or "[ ]" in val:
                    provided = True
                    checked = "[x]" in val
                elif not _is_no_answer(val) and not val.startswith("###"):
                    # If it's not a no-answer and not another question, consider it a response
                    # But be more restrictive - only if it contains checkbox-like content
                    if any(term in val for term in ["advanced", "degree", "bachelor", "master", "required", "checkbox"]):
                        provided = True
            if provided:
                data["degrees"] = ["Master's"] if checked else ["Bachelor's"]
                provided_fields.add("degrees")

        # Email
        elif "Email associated with your GitHub account" in line:
            v = next_line_value(i)
            email = v if v else "_no response_"
            if not _is_no_answer(email):
                util.setOutput("commit_email", email)
                util.setOutput("commit_username", username)
            else:
                util.setOutput("commit_email", "action@github.com")
                util.setOutput("commit_username", "GitHub Action")

    # Handle removal checkbox for edits
    if is_edit:
        for i, line in enumerate(lines):
            if "Permanently remove this internship from the list?" in line:
                if i + 1 < len(lines):
                    data["is_visible"] = "[x]" not in lines[i + 1].lower()
                    provided_fields.add("is_visible")
                break

    # If NEW and category still not set, try classifier or fallback
    if not is_edit and "category" not in data:
        if "title" in data:
            try:
                data["category"] = util.classifyJobCategory(data) or "Other"
            except Exception:
                data["category"] = "Other"
        else:
            data["category"] = "Other"
        provided_fields.add("category")

    # Store which fields were provided for selective updates in edits
    data["_provided_fields"] = provided_fields

    return data


def main():
    try:
        event_file_path = sys.argv[1]

        with open(event_file_path) as f:
            event_data = json.load(f)
    except Exception as e:
        util.fail(f"Failed to read event file: {str(e)}")
        return

    try:
        # CHECK IF NEW OR OLD INTERNSHIP OR BULK MARK INACTIVE
        labels = [label["name"] for label in event_data["issue"]["labels"]]
        print(f"DEBUG: Issue labels found: {labels}")
        
        new_internship = "new_internship" in labels
        edit_internship = "edit_internship" in labels
        bulk_mark_inactive = "bulk_mark_inactive" in labels

        # If it's a bulk_mark_inactive issue, delegate to that script
        if bulk_mark_inactive:
            print("DEBUG: Detected bulk_mark_inactive issue, delegating to bulk_mark_inactive.py")
            import subprocess
            
            # Run the script without capturing output so it can write directly to GITHUB_OUTPUT
            result = subprocess.run(
                ["python", ".github/scripts/bulk_mark_inactive.py", event_file_path]
            )
            print(f"DEBUG: bulk_mark_inactive.py returncode: {result.returncode}")
            
            # Exit with the same return code
            sys.exit(result.returncode)

        if not new_internship and not edit_internship:
            util.fail(f"Only new_internship, edit_internship, and bulk_mark_inactive issues can be approved. Found labels: {labels}")
            return

        # GET DATA FROM ISSUE FORM
        issue_body = event_data['issue']['body']
        issue_user = event_data['issue']['user']['login']

        data = getData(issue_body, is_edit=edit_internship, username=issue_user)
    except Exception as e:
        util.fail(f"Error processing issue data: {str(e)}")
        return

    if new_internship:
        data["source"] = issue_user
        data["id"] = str(uuid.uuid4())
        data["date_posted"] = int(datetime.now().timestamp())
        data["company_url"] = ""
        data["is_visible"] = True

    # remove utm-source
    if "url" in data:
        utm = data["url"].find("?utm_source")
        if utm == -1:
            utm = data["url"].find("&utm_source")
        if utm != -1:
            data["url"] = data["url"][:utm]

    # Remove the internal tracking field before saving
    provided_fields = data.pop("_provided_fields", set())

    # UPDATE LISTINGS
    def get_commit_text(listing):
        closed_text = "" if listing["active"] else "(Closed)"
        sponsorship_text = "" if listing["sponsorship"] == "Other" else ("(" + listing["sponsorship"] + ")")
        parts = [listing["title"].strip(), "at", listing["company_name"].strip()]
        if closed_text:
            parts.append(closed_text)
        if sponsorship_text:
            parts.append(sponsorship_text)
        listing_text = " ".join(parts)
        return listing_text

    try:
        with open(".github/scripts/listings.json", "r") as f:
            listings = json.load(f)

        if listing_to_update := next(
            (item for item in listings if item["url"] == data["url"]), None
        ):
            if new_internship:
                util.fail("This internship is already in our list. See CONTRIBUTING.md for how to edit a listing")
                return
            
            # FIXED: Only update fields that were explicitly provided in the edit form
            # This preserves existing category, degrees, sponsorship, etc. when not updated
            for key, value in data.items():
                if key in provided_fields or key in ["date_updated"]:  # Always update date_updated
                    listing_to_update[key] = value

            util.setOutput("commit_message", "updated listing: " + get_commit_text(listing_to_update))
        else:
            if edit_internship:
                util.fail("We could not find this internship in our list. Please double check you inserted the right url")
                return
            listings.append(data)

            util.setOutput("commit_message", "added listing: " + get_commit_text(data))

        with open(".github/scripts/listings.json", "w") as f:
            f.write(json.dumps(listings, indent=4))
    except Exception as e:
        util.fail(f"Error updating listings: {str(e)}")
        return


if __name__ == "__main__":
    main()