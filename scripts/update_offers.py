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


def parse_budgetdranken_product(url: str):
    print(f"\n[BudgetDranken] Fetching: {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ------------------------------
    # TITLE
    # ------------------------------
    title_el = (
        soup.select_one("h1.page-title span.base")
        or soup.select_one("h1.page-title")
        or soup.select_one("h1")
    )
    title = title_el.get_text(strip=True) if title_el else None

    # ------------------------------
    # TRUE PRICE (data-price-amount)
    # ------------------------------
    price = None
    old_price = None

    price_wrapper = soup.select_one('[data-price-type="finalPrice"]')
    old_price_wrapper = soup.select_one('[data-price-type="oldPrice"]')

    # Read correct price
    if price_wrapper and price_wrapper.has_attr("data-price-amount"):
        try:
            price = float(price_wrapper["data-price-amount"])
        except Exception:
            price = None

    # Read old price only if it exists
    if old_price_wrapper and old_price_wrapper.has_attr("data-price-amount"):
        try:
            old_price = float(old_price_wrapper["data-price-amount"])
        except Exception:
            old_price = None

    # Debug logging
    print(f"  ↳ Title: {title}")
    print(f"  ↳ Final price (correct): {price}")
    print(f"  ↳ Old price: {old_price}")

    # Protection: never accept €<5 (shipping/statiegeld)
    if price is not None and price < 5:
        print("  ❌ Invalid price (<5) — likely shipping/statiegeld. Ignored.")
        price = None

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

        # Only process BudgetDranken URLs
        if "budgetdranken.nl" in domain:
            title, price, old_price = parse_budgetdranken_product(url)

            # Title update
            if title and title != offer.get("title"):
                print(f"  ✔ Updating title: {offer['title']} → {title}")
                offer["title"] = title
                changed = True

            # Price update
            if price is not None and price != offer.get("price"):
                print(f"  ✔ Updating price: {offer.get('price')} → {price}")
                offer["price"] = price
                changed = True

            # Old price update
            if old_price is not None and old_price != offer.get("oldPrice"):
                print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
                offer["oldPrice"] = old_price
                changed = True

            if price is None:
                print("  ❌ WARNING: Could not parse correct price — keeping existing value")

    # Save output file if changed
    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
