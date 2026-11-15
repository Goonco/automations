import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright
from pydantic import TypeAdapter
from record import Prices, Record, Status

CSV_PATH = Path("records.csv")
MIN_CSV_PATH = Path("min.csv")
RECORD_FIELDS = list(Record.__annotations__)

EXTRACT_JS = r"""
() => {
    const times = [...document.querySelectorAll(
        '[data-e2e="search-result-departure-time"] time'
    )];

    const matches = times.filter(
        el => el.textContent.trim() === "11:35 PM"
    );

    const prices = matches.map(el => {
        const row = el.closest(
            '[class*="SearchResult__rowRideAndPrice"]'
        );

        const label = row?.querySelector(
            '[data-type="priceButton"]'
        )?.getAttribute("aria-label");

        const m = label?.match(
            /\$([\d,]+)\.(\d{2})\s+per person/i
        );

        return m
            ? Number(m[1].replace(/,/g, "")) * 100
                + Number(m[2])
            : null;
    });

    return prices.includes(null) ? [] : prices;
}
"""


prices_adapter = TypeAdapter(Prices)
record_adapter = TypeAdapter(Record)


def fetch_prices() -> Prices:
    URL = "https://shop.greyhound.com/search?" + urlencode(
        {
            "departureCity": "97a51149-150b-4ecf-a1fa-aadaeb61bf02",
            "arrivalCity": "06b24219-e696-432e-9d86-694d0b60e6c3",
            "rideDate": "24.11.2026",
            "adult": "2",
        }
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            try:
                context = browser.new_context()
                page = context.new_page()

                page.goto(URL, wait_until="domcontentloaded")

                page.wait_for_selector(
                    '[data-e2e="search-result-departure-time"]', timeout=30000
                )

                raw = page.evaluate(EXTRACT_JS)

                return prices_adapter.validate_python(raw, strict=True)

            finally:
                browser.close()

    except Exception:  # noqa: BLE001
        return []


def load_min() -> Record | None:
    if not MIN_CSV_PATH.exists():
        return None

    with MIN_CSV_PATH.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f), None)

    if row is None:
        return None

    return record_adapter.validate_python(
        {**row, "prices": json.loads(row["prices"])},
        strict=True,
    )


def save_min(record: Record) -> None:
    with MIN_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        writer.writerow(record)


def append_record(record: Record) -> None:
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RECORD_FIELDS)

        if f.tell() == 0:
            writer.writeheader()

        writer.writerow(record)


def main() -> None:
    incomming_prices = fetch_prices()
    min_record = load_min()
    previous_price: Prices = min_record["prices"] if min_record is not None else []

    status: Status
    prices: Prices = incomming_prices

    update_min = False

    if len(incomming_prices) != 1:
        status = "ERROR"
    else:
        status = "OK"
        if len(previous_price) == 0 or previous_price[0] > incomming_prices[0]:
            update_min = True

    record: Record = {
        "utc": datetime.now(UTC).isoformat(),
        "status": status,
        "prices": prices,
    }

    if update_min:
        save_min(record)
    append_record(record)

    print(record)


if __name__ == "__main__":
    main()
