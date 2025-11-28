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


def parse_price(text: str):
    """Convert a price string like '€ 52,95' or '52,95' to float 52.95."""
    if not text:
        return None
    cleaned = text.replace("€", "").replace("\xa0", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    # extract first number with up to 2 decimals
    import re
    m = re.search(r"(\d+(\.\d{1,2})?)", cleaned)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_budgetdranken_product(url: str):
    """Parse a single BudgetDranken product page for title, price, oldPrice."""
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
    # PRICE (based on your theme's .price-box CSS)
    # ------------------------------
    price = None
    old_price = None

    # 1) Discounted: old-price + final-price
    final_el = soup.select_one(".price-box .old-price + .final-price .price")

    # 2) Special price (if present)
    if not final_el:
        final_el = soup.select_one(".price-box .special-price .price")

    # 3) Simple final-price (no old)
    if not final_el:
        final_el = soup.select_one(".price-box .final-price .price")

    # 4) Fallback: any .price inside .price-box
    if not final_el:
        final_el = soup.select_one(".price-box .price")

    if final_el:
        price_text = final_el.get_text(strip=True)
        price = parse_price(price_text)
        print(f"  ↳ Final price element: '{price_text}' → {price}")
    else:
        print("  ❌ No final price element found in .price-box")

    # OLD PRICE (if discounted)
    old_el = soup.select_one(".price-box .old-price .price")
    if old_el:
        old_text = old_el.get_text(strip=True)
        old_price = parse_price(old_text)
        print(f"  ↳ Old price element: '{old_text}' → {old_price}")

    print(f"  ↳ Title: {title}")
    print(f"  ↳ Parsed final price: {price}")
    print(f"  ↳ Parsed old price:   {old_price}")

    # Safety: block €1,25 etc.
    if price is not None and price < 5:
        print("  ❌ Detected price < €5 (likely statiegeld / add-on) — ignoring.")
        price = None

    return title, price, old_price


def update_offers():
    """Update offers.json in-place for all BudgetDranken URLs."""
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
        if "budgetdranken.nl" not in domain:
            # Only handle BudgetDranken in this script
            continue

        title, price, old_price = parse_budgetdranken_product(url)

        # TITLE
        if title and title != offer.get("title"):
            print(f"  ✔ Updating title: {offer['title']} → {title}")
            offer["title"] = title
            changed = True

        # PRICE
        if price is not None and price != offer.get("price"):
            print(f"  ✔ Updating price: {offer.get('price')} → {price}")
            offer["price"] = price
            changed = True

        # OLD PRICE
        if old_price is not None and old_price != offer.get("oldPrice"):
            print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
            offer["oldPrice"] = old_price
            changed = True

        if price is None:
            print("  ❌ WARNING: No valid price parsed — keeping existing value.")

    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
