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

    while len(seen) < target_count:
        page.mouse.wheel(0, 30000)
        time.sleep(2)
        cards = page.query_selector_all("a[class*='_company_i9oky_355']")
        if len(cards) == 0:
            print("Loading error! retry to scrape.....")
            continue
        for card in cards:
            href = card.get_attribute("href")
            if href and "/companies/" in href:
                seen.add(href)

        if len(seen) == last_len:
            break
        last_len = len(seen)

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
