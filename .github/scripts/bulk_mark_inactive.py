#!/usr/bin/env python3

import json
import sys
import re
from datetime import datetime
import util

def extract_urls_from_issue_body(body):
    """
    Extract URLs from the issue body, specifically from the URLs field.
    Returns a list of cleaned URLs.
    """
    urls = []
    
    # Look for the URLs section in the issue body
    # The format is typically "### Job Posting URLs\n\n[urls here]"
    lines = body.split('\n')
    in_urls_section = False
    
    for line in lines:
        line = line.strip()
        
        # Check if we're entering the URLs section
        if 'Job Posting URLs' in line:
            in_urls_section = True
            continue
            
        # Check if we're leaving the URLs section (next field starts)
        if in_urls_section and line.startswith('###'):
            break
            
        # If we're in the URLs section and line looks like a URL
        if in_urls_section and line:
            # Skip empty lines and markdown formatting
            if line.startswith('http'):
                # Clean the URL - remove any trailing characters that might have been added
                clean_url = line.strip()
                
                # Remove tracking parameters (UTM and ref parameters)
                # Check for various tracking parameters in order of preference
                tracking_params = ["?utm_source", "&utm_source", "?ref=", "&ref="]
                earliest_pos = len(clean_url)
                
                for param in tracking_params:
                    pos = clean_url.find(param)
                    if pos != -1 and pos < earliest_pos:
                        earliest_pos = pos
                
                if earliest_pos < len(clean_url):
                    clean_url = clean_url[:earliest_pos]
                    
                urls.append(clean_url)
    
    return urls

def extract_reason_from_issue_body(body):
    """
    Extract the reason from the issue body.
    """
    lines = body.split('\n')
    in_reason_section = False
    reason_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # Check if we're entering the reason section
        if 'Reason for marking as inactive' in line:
            in_reason_section = True
            continue
            
        # Check if we're leaving the reason section (next field starts)
        if in_reason_section and line_stripped.startswith('###'):
            break
            
        # If we're in the reason section, collect the text
        if in_reason_section and line_stripped:
            reason_lines.append(line_stripped)
    
    return ' '.join(reason_lines) if reason_lines else "Bulk marking as inactive"

def extract_email_from_issue_body(body):
    """
    Extract email from the issue body if provided.
    """
    lines = body.split('\n')
    in_email_section = False
    
    for line in lines:
        line_stripped = line.strip()
        
        # Check if we're entering the email section
        if 'Email associated with your GitHub account' in line:
            in_email_section = True
            continue
            
        # Check if we're leaving the email section
        if in_email_section and line_stripped.startswith('###'):
            break
            
        # If we're in the email section and line looks like an email
        if in_email_section and line_stripped and '@' in line_stripped:
            return line_stripped
    
    return None

def mark_urls_as_inactive(urls):
    """
    Mark the given URLs as inactive in listings.json.
    Returns a dictionary with results for each URL.
    """
    results = {}
    
    try:
        # Load current listings
        with open(".github/scripts/listings.json", "r") as f:
            listings = json.load(f)
    except Exception as e:
        util.fail(f"Failed to load listings.json: {str(e)}")
        return results
    
    # Process each URL
    for url in urls:
        try:
            # Find the listing with this URL
            listing_found = False
            for listing in listings:
                if listing.get("url") == url:
                    listing_found = True
                    
                    # Check if already inactive
                    if not listing.get("active", True):
                        results[url] = {
                            "status": "warning",
                            "message": f"Already inactive: {listing['company_name']} - {listing['title']}"
                        }
                    else:
                        # Mark as inactive and update timestamp
                        listing["active"] = False
                        listing["date_updated"] = int(datetime.now().timestamp())
                        results[url] = {
                            "status": "success",
                            "message": f"Marked inactive: {listing['company_name']} - {listing['title']}"
                        }
                    break
            
            if not listing_found:
                results[url] = {
                    "status": "error",
                    "message": f"URL not found in database: {url}"
                }
                
        except Exception as e:
            results[url] = {
                "status": "error",
                "message": f"Error processing URL: {str(e)}"
            }
    
    # Save the updated listings
    try:
        with open(".github/scripts/listings.json", "w") as f:
            json.dump(listings, f, indent=4)
    except Exception as e:
        util.fail(f"Failed to save listings.json: {str(e)}")
        return results
    
    return results

def generate_commit_message(results, reason):
    """
    Generate a commit message based on the results.
    """
    successful_count = len([r for r in results.values() if r["status"] == "success"])
    total_count = len(results)
    
    if successful_count == 0:
        return f"Bulk inactive attempt: 0/{total_count} roles updated"
    elif successful_count == total_count:
        return f"Bulk marked inactive: {successful_count} roles - {reason}"
    else:
        return f"Bulk marked inactive: {successful_count}/{total_count} roles - {reason}"

def generate_summary_comment(results, reason):
    """
    Generate a summary comment for the GitHub issue.
    """
    successful = [url for url, result in results.items() if result["status"] == "success"]
    warnings = [url for url, result in results.items() if result["status"] == "warning"]
    errors = [url for url, result in results.items() if result["status"] == "error"]
    
    comment = f"## Bulk Mark Inactive Results\n\n"
    comment += f"**Reason:** {reason}\n\n"
    comment += f"**Summary:** {len(successful)} successful, {len(warnings)} warnings, {len(errors)} errors\n\n"
    
    if successful:
        comment += f"### ✅ Successfully Marked Inactive ({len(successful)})\n"
        for url in successful:
            comment += f"- {results[url]['message']}\n"
        comment += "\n"
    
    if warnings:
        comment += f"### ⚠️ Warnings ({len(warnings)})\n"
        for url in warnings:
            comment += f"- {results[url]['message']}\n"
        comment += "\n"
    
    if errors:
        comment += f"### ❌ Errors ({len(errors)})\n"
        for url in errors:
            comment += f"- {results[url]['message']}\n"
        comment += "\n"
    
    if successful:
        comment += "The README will be updated automatically.\n"
    
    return comment

def main():
    try:
        event_file_path = sys.argv[1]
        
        with open(event_file_path) as f:
            event_data = json.load(f)
    except Exception as e:
        util.fail(f"Failed to read event file: {str(e)}")
        return
    
    try:
        # Check if this is a bulk_mark_inactive issue
        labels = [label["name"] for label in event_data["issue"]["labels"]]
        if "bulk_mark_inactive" not in labels:
            util.fail("This script only processes bulk_mark_inactive issues")
            return
        
        # Extract data from issue body
        issue_body = event_data['issue']['body']
        issue_user = event_data['issue']['user']['login']
        
        urls = extract_urls_from_issue_body(issue_body)
        reason = extract_reason_from_issue_body(issue_body)
        email = extract_email_from_issue_body(issue_body)
        
        if not urls:
            util.fail("No valid URLs found in the issue body")
            return
        
        print(f"Processing {len(urls)} URLs...")
        
        # Process the URLs
        results = mark_urls_as_inactive(urls)
        
        # Generate outputs for GitHub Actions
        commit_message = generate_commit_message(results, reason)
        summary_comment = generate_summary_comment(results, reason)
        
        # Set outputs for GitHub Actions
        util.setOutput("commit_message", commit_message)
        util.setOutput("summary_comment", summary_comment)
        
        # Set commit author info
        if email:
            util.setOutput("commit_email", email)
            util.setOutput("commit_username", issue_user)
        else:
            util.setOutput("commit_email", "action@github.com")
            util.setOutput("commit_username", "Github Action")
        
        # Print results for debugging
        print("Results:")
        for url, result in results.items():
            print(f"  {result['status'].upper()}: {result['message']}")
        
        # Check if any URLs were successfully processed
        successful_count = len([r for r in results.values() if r["status"] == "success"])
        if successful_count == 0:
            util.fail("No URLs were successfully marked as inactive")
            return
            
    except Exception as e:
        util.fail(f"Error processing bulk mark inactive: {str(e)}")
        return

if __name__ == "__main__":
    main()
