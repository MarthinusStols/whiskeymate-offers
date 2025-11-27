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


def extract_json_ld(soup: BeautifulSoup):
    """Extract JSON-LD that contains product + offers info."""
    json_ld_tags = soup.find_all("script", {"type": "application/ld+json"})

    for tag in json_ld_tags:
        try:
            data = json.loads(tag.string.strip())

            # Some BD pages return a list of multiple JSON-LD objects
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "offers" in item:
                        return item

            # Single object
            if isinstance(data, dict) and "offers" in data:
                return data

        except Exception:
            continue

    return None


def parse_budgetdranken_product(url: str):
    print(f"\n[BudgetDranken] Fetching: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- JSON-LD extraction (MAIN METHOD) ---
    product_json = extract_json_ld(soup)

    if product_json:
        title = product_json.get("name", None)

        offers = product_json.get("offers", {})
        price = None
        old_price = None

        # Normal price
        if "price" in offers:
            try:
                price = float(offers["price"])
            except ValueError:
                pass

        # Discounted items (Magento uses lowPrice / highPrice)
        if "lowPrice" in offers:
            price = float(offers["lowPrice"])
        if "highPrice" in offers:
            old_price = float(offers["highPrice"])

        print(f"  ↳ JSON-LD title: {title}")
        print(f"  ↳ JSON-LD price: {price}")
        print(f"  ↳ JSON-LD oldPrice: {old_price}")

        # JSON-LD is ALWAYS correct for BD → return immediately
        return title, price, old_price

    print("  ⚠️ JSON-LD missing — falling back to HTML scrapers")

    # ------------------------------------------------------------------
    # FALLBACK HTML PARSER (only used if JSON-LD fails)
    # ------------------------------------------------------------------

    title_el = (
        soup.select_one("h1.page-title span.base")
        or soup.select_one("h1.page-title")
        or soup.select_one("h1")
    )
    title = title_el.get_text(strip=True) if title_el else None

    price_el = soup.select_one('[data-price-type="finalPrice"] .price')
    old_price_el = soup.select_one('[data-price-type="oldPrice"] .price')

    price = parse_price(price_el.get_text()) if price_el else None
    old_price = parse_price(old_price_el.get_text()) if old_price_el else None

    print(f"  ↳ Fallback HTML title: {title}")
    print(f"  ↳ Fallback HTML final: {price}")
    print(f"  ↳ Fallback HTML old:   {old_price}")

    # FINAL PROTECTION: never accept price < €5 (shipping, deposits)
    if price is not None and price < 5:
        print("  ❌ Invalid fallback price (<5) blocked")
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

            # -- TITLE --
            if title and title != offer.get("title"):
                print(f"  ✔ Updating title: {offer['title']} → {title}")
                offer["title"] = title
                changed = True

            # -- PRICE --
            if price is not None and price != offer.get("price"):
                print(f"  ✔ Updating price: {offer.get('price')} → {price}")
                offer["price"] = price
                changed = True

            # -- OLD PRICE (discount) --
            if old_price is not None and old_price != offer.get("oldPrice"):
                print(f"  ✔ Updating oldPrice: {offer.get('oldPrice')} → {old_price}")
                offer["oldPrice"] = old_price
                changed = True

            if price is None:
                print("  ❌ WARNING: No valid price found — keeping existing value")

    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
