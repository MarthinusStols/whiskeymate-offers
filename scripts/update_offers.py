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


def parse_price_float(value):
    """Convert price strings or floats to float."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        # Handle "58,95"
        value = value.replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None


def extract_hyva_old_price(el):
    """
    Extract old price from Hyvä style:
    x-html="hyva.formatPrice(58.95 + getCustomOptionPrice())"
    """
    if not el:
        return None

    attr = el.get("x-html")
    if not attr:
        return None

    # Extract first float inside the JS expression
    match = re.search(r"(\d+\.\d+)", attr)
    if match:
        return float(match.group(1))

    return None


def parse_budgetdranken_product(url: str):
    print(f"\n[BudgetDranken] Fetching: {url}")

    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ------------------------------------------------
    # MAIN PRICE (server-rendered)
    # ------------------------------------------------
    data_div = soup.select_one("div[data-product_id]")
    if not data_div:
        print("  ❌ No data-product block found.")
        return None, None, None

    title = data_div.get("data-item_name")
    price_raw = data_div.get("data-price")  # always present

    price = parse_price_float(price_raw)

    print(f"  ↳ Title: {title}")
    print(f"  ↳ data-price: {price_raw} → {price}")

    if price is not None and price < 5:
        print("  ❌ Price < €5 detected — statiegeld/add-on. Ignored.")
        price = None

    # ------------------------------------------------
    # OLD PRICE (Hyvä JS-driven price)
    # ------------------------------------------------
    old_price = None

    old_price_el = soup.select_one(".old-price .price")

    if old_price_el:
        text_value = old_price_el.get_text(strip=True)

        if text_value:
            # Sometimes Hyvä fills text, sometimes empty
            old_price = parse_price_float(text_value)
            print(f"  ↳ Old price (text): {text_value} → {old_price}")
        else:
            # Extract from x-html expression
            extracted = extract_hyva_old_price(old_price_el)
            if extracted:
                old_price = extracted
                print(f"  ↳ Old price extracted from x-html → {old_price}")
            else:
                print("  ↳ Old price present but empty — no x-html value extracted")

    else:
        print("  ↳ No .old-price element on page")

    print(f"  ↳ Final parsed price: {price}")
    print(f"  ↳ Final parsed old price: {old_price}")

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

        if "budgetdranken.nl" not in url.lower():
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

    if changed:
        with OFFERS_PATH.open("w", encoding="utf-8") as f:
            json.dump(offers, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("\n✔ offers.json updated.")
    else:
        print("\nNo changes detected.")


if __name__ == "__main__":
    update_offers()
