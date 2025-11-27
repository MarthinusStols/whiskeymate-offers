import json
import re
import sys
from pathlib import Path

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
    Convert a price string like '€34,95' or '34,95' to float 34.95
    """
    if not text:
        return None
    # remove euro sign and spaces
    cleaned = text.replace("€", "").replace("\xa0", "").strip()
    # turn 34,95 into 34.95
    cleaned = cleaned.replace(".", "").replace(",", ".")
    m = re.search(r"(\d+(\.\d{1,2})?)", cleaned)
    if not m:
        return None
    return float(m.group(1))


def fetch_prices(url: str):
    """
    Fetch current price and old price from a DrankDozijn product page.

    NOTE: The CSS selectors here may need tweaking if DrankDozijn
    changes their HTML. If you see 'Could not find price' in the logs,
    inspect the page HTML and adjust selectors.
    """
    print(f"Fetching {url}")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Try a few common selectors – adjust if needed
    # current price
    price_el = (
        soup.select_one("[itemprop=price]")
        or soup.select_one(".price-current")
        or soup.select_one(".product-price__main")
        or soup.select_one(".product-price")
    )

    # old price (striked through / from-price)
    old_el = (
        soup.select_one(".price-old")
        or soup.select_one(".product-price__old")
        or soup.select_one(".old-price")
    )

    price = parse_price(price_el.get_text(strip=True)) if price_el else None
    old_price = parse_price(old_el.get_text(strip=True)) if old_el else None

    if price is None:
        print(f"  ⚠️  Could not find price on page: {url}")

    return price, old_price


def main():
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

        try:
            price, old_price = fetch_prices(url)
        except Exception as e:
            print(f"  ❌ Error fetching {url}: {e}")
            continue

        if price is not None and price != offer.get("price"):
            print(f"  ✅ Updating price {offer.get('price')} → {price}")
            offer["price"] = price
            changed = True

        if old_price is not None and old_price != offer.get("oldPrice"):
            print(f"  ✅ Updating oldPrice {offer.get('oldPrice')} → {old_price}")
            offer["oldPrice"] = old_price
            changed = True

    if not changed:
        print("No price changes detected.")
        return

    with OFFERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("offers.json updated.")


if __name__ == "__main__":
    main()

