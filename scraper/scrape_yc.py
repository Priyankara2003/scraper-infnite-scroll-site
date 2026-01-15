import json
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.ycombinator.com"
OUTPUT_PATH = "data/yc_startups.csv"
CSV_PATH = "data/yc_startups.csv"
JSON_PATH = "data/companies.json"

# load scraped data using csv scraped data
def load_scraped_links():
    if not os.path.exists(CSV_PATH):
        return set()
    df = pd.read_csv(CSV_PATH)
    return set(df["Profile URL"].tolist())

# add data one by one
def append_to_csv(data):
    df = pd.DataFrame([data])
    df.to_csv(CSV_PATH, mode='a', header=not os.path.exists(CSV_PATH), index=False)

# handle infinite scroll and extract links for scraping
def scroll_and_collect_links(page, target_count):
    seen = set()
    last_len = 0
    retry_count = 0
    max_retries = 10

    while len(seen) < target_count:
        page.mouse.wheel(0, 30000)
        time.sleep(3)
        
        # Try multiple selector strategies
        cards = page.query_selector_all("a[href*='/companies/']")
        
        if len(cards) == 0:
            retry_count += 1
            print(f"Loading error! retry {retry_count}/{max_retries} to scrape.....")
            
            # Debug: save page content to see what's actually there
            if retry_count == 3:
                print("Saving page HTML for debugging...")
                with open("data/debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print("Page HTML saved to data/debug_page.html")
            
            if retry_count >= max_retries:
                print("Max retries reached. Stopping.")
                break
            continue
        
        retry_count = 0  # Reset on success
        for card in cards:
            href = card.get_attribute("href")
            if href and "/companies/" in href and not href.startswith("http"):
                seen.add(href)

        print(f"Found {len(seen)} company links so far...")
        if len(seen) == last_len:
            break
        last_len = len(seen)

    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    
    with open(JSON_PATH, "w") as f:
        json.dump(list(seen)[:target_count], f, indent=2)

# dive through separate links and retrieve data what we want
def extract_profile_data(page, url):
    try:
        name = page.query_selector("h1.text-3xl.font-bold")
        name = name.inner_text().strip() if name else ""
        desc = page.query_selector("div.prose.max-w-full.whitespace-pre-line")
        desc = desc.inner_text().strip() if desc else ""
        batch = page.query_selector("div.ycdc-card-new span.whitespace-nowrap")
        batch = batch.inner_text().strip() if batch else ""

        founders = []
        linkedins = []

        cards = page.query_selector_all("div.ycdc-card-new.w-full.space-y-1\\.5")
        for card in cards:
            nameLink = card.inner_text().strip()  # fallback if LinkedIn text missing

            # Try to find LinkedIn link inside the card
            link = card.query_selector("a[href*='linkedin.com']")
            if link:
                linkedin_url = link.get_attribute("href")
                linked_text = link.inner_text().strip()

                # Use link text as name if available, otherwise fallback
                founder_name = linked_text if linked_text else nameLink
            else:
                linkedin_url = ""
                founder_name = nameLink

            founders.append(nameLink)
            linkedins.append(linkedin_url)

        return {
            "Company Name": name,
            "Batch": batch,
            "Description": desc,
            "Founders": ", ".join(founders),
            "LinkedIn URLs": ", ".join(linkedins),
            "Profile URL": url
        }
    except Exception as e:
        print("An error occurred:", str(e))
        return {
            "Company Name": "", "Batch": "", "Description": "",
            "Founders": "", "LinkedIn URLs": "", "Profile URL": url
        }

def main():

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Visit YC company directory
        page.goto(BASE_URL + "/companies", timeout=60000)

        if not os.path.exists(JSON_PATH):
            scroll_and_collect_links(page=page,target_count=500)

        with open(JSON_PATH, "r") as f:
            urls = json.load(f)

        already_scraped = load_scraped_links()

        # Scroll and collect profile page URLs
        print("📥 Scrolling and collecting profile URLs...")
        profile_paths = urls
        print(f"✅ Collected {len(profile_paths)} company profile links.")

        # Visit each company profile and extract data
        print("🔍 Visiting profile pages...")
        for i, path in enumerate(profile_paths, 1):
            full_url = BASE_URL + path
            if full_url in already_scraped:
                print(f"✅ Already scraped: {full_url}")
                continue

            print(f"[{i}/{len(profile_paths)}] Scraping {full_url}")
            profile_page = context.new_page()
            profile_page.goto(full_url, timeout=600000)
            company_data = extract_profile_data(profile_page, full_url)

            # Step 4: Save to CSV
            append_to_csv(company_data)
            print(f"✅ Scraped and saved: {full_url}")
            profile_page.close()
            time.sleep(1.5)  # polite delay

        print(f"✅ Done. Data saved to {OUTPUT_PATH}")

        browser.close()

if __name__ == "__main__":
    main()
