import json
import sys
import re
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
    # FIX: ONLY look inside .product-info-price
    # This BLOCK contains the REAL whisky price
    # ------------------------------
    info_block = soup.select_one(".product-info-price")
    if not info_block:
        print("  ❌ ERROR: .product-info-price block not found")
        return title, None, None

    price = None
    old_price = None

    # FINAL PRICE (real bottle price)
    final_el = info_block.select_one('[data-price-type="finalPrice"]')
    if final_el and final_el.has_attr("data-price-amount"):
        try:
            price = float(final_el["data-price-amount"])
        except:
            price = None

    # OLD PRICE (only exists if discounted)
    old_el = info_block.select_one('[data-price-type="oldPrice"]')
    if old_el and old_el.has_attr("data-price-amount"):
        try:
            old_price = float(old_el["data-price-amount"])
        except:
            old_price = None

    print(f"  ↳ Title: {title}")
    print(f"  ↳ Final price (correct): {price}")
    print(f"  ↳ Old price: {old_price}")

    # SAFETY: Reject €1.25 or anything under €5
    if price is not None and price < 5:
        print("  ❌ Detected price < €5 (statiegeld / add-on) — ignoring")
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

        # Only scrape BudgetDranken
        if "budgetdranken.nl" in domain:
            title, price, old_price = parse_budgetdranken_product(url)

            # TITLE UPDATE
            if title and title != offer.get("title"):
                print(f"  ✔ Updating title: {offer['title']} → {title}")
                offer["title"] = title
                changed = True

            # PRICE UPDATE
            if price is not None and price != offer.get("price"):
                print(f"  ✔ Updating price: {offer.get('price')} → {price}")
                offer["price"] = price
                changed = True

            # OLD PRICE UPDATE
            if old_price is not None and old_price != offer.get("oldPrice"):
                print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
                offer["oldPrice"] = old_price
                changed = True

            if price is None:
                print("  ❌ WARNING: Could not parse valid price — kept old value")

    # SAVE FILE IF CHANGED
    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
