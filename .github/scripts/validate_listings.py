import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver

# Set up headless Selenium driver
options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
driver = webdriver.Chrome(options=options)

DEAD_REGEX = [
    r"no longer accepting", 
    r"position .* filled",
    r"doesn'?t exist",
    r"job .* closed",
    r"no longer available"
]

def shortenTitle(title: str):
    return title.split("–")[0].split(" - ")[0]

def is_listing_active(listing):
    link = listing["url"]
    try:
        response = requests.get(link, timeout=10)
        
        # If page returns 404 or redirects immediately
        if response.status_code == 404 or "job_closed" in response.url:
            return False

        driver.get(link)
        time.sleep(3)  

        page = driver.page_source
        soup = BeautifulSoup(page, 'html.parser')
        page_text = soup.get_text().strip().lower()

        if any(re.search(pattern, page_text) for pattern in DEAD_REGEX):
            return False
        
        return True
    except requests.RequestException:
        return False  

def update_listings_activity():
    """Reads listings.json and marks closed jobs as inactive."""
    json_file = "listings.json"
    
    with open(json_file, "r", encoding="utf-8") as f:
        listings = json.load(f)

    # closed_listings = []
    updated = False  
    for listing in listings:
        listing["title"] = shortenTitle(listing["title"])
        if listing["source"] == "Simplify" or listing["active"] == False: 
            continue

        if not is_listing_active(listing):
            listing["active"] = False
            print("Found inactive listing: " + listing["company_name"] + " | " + listing["title"])
            # closed_listings.append(listing) 
            updated = True
    # updates listings.json directly 
    if updated:
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(listings, f, indent=4)


if __name__ == "__main__":
    update_listings_activity()
    driver.quit()  