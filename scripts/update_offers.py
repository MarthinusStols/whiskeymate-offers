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
    """Convert a price string like '€ 52,95' to float 52.95"""
    if not text:
        return None
    cleaned = text.replace("€", "").replace("\xa0", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    m = re.search(r"(\d+(\.\d{1,2})?)", cleaned)
    if not m:
        return None
    return float(m.group(1))


def parse_budgetdranken_product(url: str):
    print(f"\n[BudgetDranken] Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # --- TITLE ---
    title_el = (
        soup.select_one("h1.page-title span.base")
        or soup.select_one("h1.page-title")
        or soup.select_one("h1")
    )
    title = title_el.get_text(strip=True) if title_el else None
    print(f"  ↳ Title found: {title}")

    # --- PRICE (correct Magento selector) ---
    price_el = soup.select_one('[data-price-type="finalPrice"] .price')
    old_price_el = soup.select_one('[data-price-type="oldPrice"] .price')

    price = parse_price(price_el.get_text()) if price_el else None
    old_price = parse_price(old_price_el.get_text()) if old_price_el else None

    # Debug logging
    print(f"  ↳ Raw final price: {price_el.get_text(strip=True) if price_el else 'NONE'}")
    print(f"  ↳ Raw old price:   {old_price_el.get_text(strip=True) if old_price_el else 'NONE'}")

    # --- FALLBACK 1: Magento fallback class ---
    if price is None:
        fallback = soup.select_one('.price-final_price .price')
        if fallback:
            price = parse_price(fallback.get_text())
            print(f"  ↳ Fallback price-final_price: {price}")

    # --- FALLBACK 2: Direct span.price (ONLY if one price exists) ---
    # This avoids accidental scraping of €1,25 shipping, etc.
    if price is None:
        candidates = soup.select("span.price")
        cleaned = []
        for c in candidates:
            value = parse_price(c.get_text())
            if value and value > 5:  # Ignore shipping like €1.25
                cleaned.append(value)
        if len(cleaned) == 1:
            price = cleaned[0]
            print(f"  ↳ Fallback: single span.price = {price}")

    # This ensures we NEVER store invalid prices (below €5)
    if price is not None and price < 5:
        print("  ❌ WARNING: Ignoring invalid price under €5 (shipping/packaging)")
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

        if "budgetdranken.nl" in domain:
            title, price, old_price = parse_budgetdranken_product(url)

            # Update title
            if title and title != offer.get("title"):
                print(f"  ✔ Updating title: {offer['title']} → {title}")
                offer["title"] = title
                changed = True

            # Update price (only if valid)
            if price is not None and price != offer.get("price"):
                print(f"  ✔ Updating price: {offer.get('price')} → {price}")
                offer["price"] = price
                changed = True

            # Update oldPrice
            if old_price is not None and old_price != offer.get("oldPrice"):
                print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
                offer["oldPrice"] = old_price
                changed = True

            # If price could not be parsed
            if price is None:
                print("  ❌ Final price could NOT be parsed — leaving existing value untouched")

    # Write back file
    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
