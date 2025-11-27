import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

OFFERS_PATH = Path("offers.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def parse_price(text: str):
    """
    Convert a price string like '€ 40,60' or '40,60' to float 40.60
    """
    if not text:
        return None
    cleaned = text.replace("€", "").replace("\xa0", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    m = re.search(r"(\d+(\.\d{1,2})?)", cleaned)
    if not m:
        return None
    return float(m.group(1))


def parse_budgetdranken_product(url: str):
    """
    Fetch current name and (incl. VAT) price / oldPrice from a BudgetDranken product page.
    Example: https://www.budgetdranken.nl/laphroaig-10yo-single-malt-0-70ltr
    """
    print(f"[BudgetDranken] Fetching {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # --- Title ---
    # Magento-style: <h1 class="page-title"><span class="base">…</span></h1>
    title_el = (
        soup.select_one("h1.page-title span.base")
        or soup.select_one("h1.page-title")
        or soup.select_one("h1")
        or soup.select_one("title")
    )
    title = title_el.get_text(strip=True) if title_el else None

    # --- Prices (incl. VAT) ---
    # On product pages, you typically see lines like:
    #   € 45,85
    #   € 40,60
    #   Koop 6 voor € 39,40 ...
    #
    # We only want the first 1–2 base prices (normal + special),
    # NOT the "Koop 6 voor" multi-bottle prices.
    text_nodes = soup.find_all(string=re.compile("€"))
    found_prices = []

    for node in text_nodes:
        txt = node.strip()
        # Skip obvious multi-bottle discount lines
        if "Koop" in txt:
            continue
        p = parse_price(txt)
        if p is not None:
            found_prices.append(p)
        if len(found_prices) >= 2:
            break

    price = None
    old_price = None

    if len(found_prices) == 1:
        # Only one price → current price, no oldPrice
        price = found_prices[0]
    elif len(found_prices) >= 2:
        # Two prices: assume highest = oldPrice, lowest = current special price
        high = max(found_prices[0], found_prices[1])
        low = min(found_prices[0], found_prices[1])
        old_price = high
        price = low

    if price is None:
        print(f"  ⚠️ Could not parse price for BudgetDranken URL: {url}")

    return title, price, old_price


def update_offers():
    if not OFFERS_PATH.exists():
        print("offers.json not found")
        sys.exit(1)

    with OFFERS_PATH.open(encoding="utf-8") as f:
        offers = json.load(f)

    changed = False

    for offer in offers:
        url = offer.get("url")
        if not url:
            continue

        domain = urlparse(url).netloc.lower()

        # Only handle BudgetDranken entries here
        if "budgetdranken.nl" in domain:
            try:
                title, price, old_price = parse_budgetdranken_product(url)
            except Exception as e:
                print(f"  ❌ Error fetching BudgetDranken URL {url}: {e}")
                continue

            # Update title if site title exists + changed
            if title and title != offer.get("title"):
                print(f"  ✅ Title: {offer.get('title')} → {title}")
                offer["title"] = title
                changed = True

            # Update price (incl. VAT)
            if price is not None and price != offer.get("price"):
                print(f"  ✅ Price: {offer.get('price')} → {price}")
                offer["price"] = price
                changed = True

            # Update oldPrice if we detected a discount
            if old_price is not None and old_price != offer.get("oldPrice"):
                print(f"  ✅ Old price: {offer.get('oldPrice')} → {old_price}")
                offer["oldPrice"] = old_price
                changed = True

        else:
            # Ignore other stores in this script
            continue

    if not changed:
        print("No changes detected.")
        return

    with OFFERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("offers.json updated.")


if __name__ == "__main__":
    update_offers()
