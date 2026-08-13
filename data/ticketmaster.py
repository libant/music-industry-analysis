"""
Ticketmaster Discovery API — NYC concerts.

This is the primary data source for face-value (primary market) ticket prices.
We track these daily. Combined with haglund_model.py's resale estimates,
this gives us the buy signal: face_value << expected_resale → BUY.

API key is already registered (in .env as TICKETMASTER_API_KEY).
"""
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

API_KEY    = os.getenv("TICKETMASTER_API_KEY", "50iHMS0oKEQhJJ2rf7o691VbneEuzpEJ")
BASE       = "https://app.ticketmaster.com/discovery/v2/events.json"
CITY       = "New York"
STATE      = "NY"
CITY_POP   = 8_550_971
DAYS_AHEAD = 180


def fetch_nyc_concerts() -> list[dict]:
    """Return all upcoming NYC music events with current face-value price ranges."""
    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=DAYS_AHEAD)

    events = []
    page   = 0

    while page * 100 < 2000:
        resp = requests.get(BASE, params={
            "apikey":              API_KEY,
            "city":                CITY,
            "stateCode":           STATE,
            "classificationName":  "music",
            "startDateTime":       now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime":         cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "size":                100,
            "page":                page,
            "sort":                "date,asc",
            "includeFamily":       "no",
        }, timeout=15)

        if resp.status_code == 429:
            print("  TM rate-limit — pausing 10s")
            time.sleep(10)
            continue

        if resp.status_code == 400:
            break   # past pagination limit (TM caps at ~1000 results)

        resp.raise_for_status()
        data = resp.json()
        batch = data.get("_embedded", {}).get("events", [])
        if not batch:
            break

        for ev in batch:
            price_ranges = ev.get("priceRanges", [])
            min_price, max_price, price_type = None, None, None

            # Prefer resale price if available; fall back to standard
            for pr in sorted(price_ranges, key=lambda x: x.get("type") == "resale", reverse=True):
                if pr.get("min") is not None:
                    min_price  = float(pr["min"])
                    max_price  = float(pr.get("max") or pr["min"])
                    price_type = pr.get("type", "standard")
                    break

            atts   = ev.get("_embedded", {}).get("attractions", [])
            venues = ev.get("_embedded", {}).get("venues",      [])
            dt     = ev.get("dates", {}).get("start", {})

            events.append({
                "source":           "ticketmaster",
                "source_event_id":  ev["id"],
                "name":             ev.get("name"),
                "artist":           atts[0].get("name") if atts else None,
                "venue":            venues[0]["name"] if venues else None,
                "city":             CITY,
                "city_pop":         CITY_POP,
                "country":          "US",
                "start_date":       dt.get("localDate"),
                "start_time":       dt.get("localTime"),
                "url":              ev.get("url"),
                # current price snapshot
                "min_price":        min_price,
                "max_price":        max_price,
                "price_type":       price_type,
            })

        total_pages = data.get("page", {}).get("totalPages", 1)
        page += 1
        if page >= total_pages:
            break
        time.sleep(0.3)

    return events


def fetch_event_prices(source_event_id: str, retries: int = 3) -> dict | None:
    """Fetch current price range for a single TM event. Returns None if cancelled."""
    url = f"https://app.ticketmaster.com/discovery/v2/events/{source_event_id}.json"
    for attempt in range(retries):
        try:
            resp = requests.get(url, params={"apikey": API_KEY}, timeout=15)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                time.sleep(10)
                continue
            resp.raise_for_status()
            ev = resp.json()
            price_ranges = ev.get("priceRanges", [])
            for pr in sorted(price_ranges, key=lambda x: x.get("type") == "resale", reverse=True):
                if pr.get("min") is not None:
                    return {
                        "min_price":  float(pr["min"]),
                        "avg_price":  float(pr.get("max", pr["min"])),
                        "listing_count": None,
                        "price_type": pr.get("type"),
                    }
            return {"min_price": None, "avg_price": None, "listing_count": None, "price_type": None}
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s backoff
            else:
                return None   # give up, skip this event


if __name__ == "__main__":
    concerts = fetch_nyc_concerts()
    priced   = [c for c in concerts if c["min_price"]]
    print(f"NYC concerts: {len(concerts)} total, {len(priced)} with pricing\n")
    for c in sorted(priced, key=lambda x: x["start_date"] or "")[:15]:
        print(f"  {c['start_date']}  {str(c['artist'] or c['name']):<32}  "
              f"@{str(c['venue']):<30}  ${c['min_price']:>6.0f}  [{c['price_type']}]")
