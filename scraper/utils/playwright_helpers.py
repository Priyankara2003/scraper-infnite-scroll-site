import json
import time

OUTPUT_PATH = "data/companies.json"

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

    with open(OUTPUT_PATH, "w") as f:
        json.dump(list(seen)[:target_count], f, indent=2)

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
