import json
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


def parse_price_float(value):
    """Convert price strings or floats to valid float."""
    if value is None:
        return None

    try:
        # Already a float-like string (e.g. "52.95")
        return float(value)
    except ValueError:
        return None


def parse_budgetdranken_product(url: str):
    print(f"\n[BudgetDranken] Fetching: {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # -----------------------------------------------
    # Extract the real price from the data-product div
    # -----------------------------------------------
    data_div = soup.select_one("div[data-product_id]")

    if not data_div:
        print("  ❌ No data-product div found. Cannot extract price.")
        return None, None, None

    title = data_div.get("data-item_name")
    price_raw = data_div.get("data-price")
    old_price_raw = data_div.get("data-old_price")  # Only exists for discounted items

    print(f"  ↳ Found data-product block")
    print(f"     item_name: {title}")
    print(f"     data-price: {price_raw}")
    print(f"     data-old_price: {old_price_raw}")

    # Convert to float
    price = parse_price_float(price_raw)
    old_price = parse_price_float(old_price_raw)

    # SAFETY: never accept €1.25 / €1.50 / < €5
    if price is not None and price < 5:
        print("  ❌ Price < €5 detected (statiegeld/add-on) — ignoring it.")
        price = None

    print(f"  ↳ Parsed final price: {price}")
    print(f"  ↳ Parsed old price:   {old_price}")

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

        # Only handle BudgetDranken links
        if "budgetdranken.nl" not in domain:
            continue

        title, price, old_price = parse_budgetdranken_product(url)

        # --- UPDATE TITLE ---
        if title and title != offer.get("title"):
            print(f"  ✔ Updating title: {offer['title']} → {title}")
            offer["title"] = title
            changed = True

        # --- UPDATE PRICE ---
        if price is not None and price != offer.get("price"):
            print(f"  ✔ Updating price: {offer.get('price')} → {price}")
            offer["price"] = price
            changed = True

        # --- UPDATE OLD PRICE ---
        if old_price is not None and old_price != offer.get("oldPrice"):
            print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
            offer["oldPrice"] = old_price
            changed = True

        if price is None:
            print("  ❌ WARNING: No valid price parsed. Keeping existing value.")

    # Save JSON if changed
    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
