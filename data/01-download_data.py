"""
Daily data collection pipeline — run once per day (or schedule via cron).

Usage:
    python3 pipeline.py           # full run (discover + snapshot + enrich)
    python3 pipeline.py snapshot  # prices only (faster, skip discovery)
    python3 pipeline.py discover  # find new events only

Schedule (macOS launchd or cron):
    0 7 * * * cd /Users/victortimir/Documents/Comanche && python3 pipeline.py
"""
import sys
import time
from datetime import datetime, timezone

from db import (
    init_db, upsert_concert, insert_snapshot,
    get_upcoming_concerts, update_spotify, get_conn,
)
from ticketmaster import fetch_nyc_concerts, fetch_event_prices
from spotify_client import get_access_token, get_artist_data, face_value_to_pop_tier


def _days_until(start_date_str: str) -> int | None:
    try:
        from datetime import date
        concert = date.fromisoformat(start_date_str)
        return (concert - datetime.now(timezone.utc).date()).days
    except Exception:
        return None


# ─── Step 1: discover new events ────────────────────────────────────────────

def run_discover() -> int:
    print("Discovering NYC concerts on Ticketmaster...")
    events = fetch_nyc_concerts()
    new = sum(1 for ev in events if upsert_concert(ev))
    print(f"  {len(events)} events found, {new} new")
    return new


# ─── Step 2: daily price snapshot ───────────────────────────────────────────

def run_snapshot() -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    upcoming = get_upcoming_concerts()
    sg_events = [e for e in upcoming if e["source"] == "ticketmaster"]
    print(f"Polling prices for {len(sg_events)} upcoming events...")

    inserted = 0
    for ev in sg_events:
        du = _days_until(ev["start_date"])
        if du is None or du < 0:
            continue

        prices = fetch_event_prices(ev["source_event_id"])
        if prices is None:
            continue

        snap = {
            "source": ev["source"],
            "source_event_id": ev["source_event_id"],
            "collection_date": today,
            "days_until": du,
            **prices,
        }
        if insert_snapshot(snap):
            inserted += 1

        time.sleep(0.1)

    print(f"  {inserted} new snapshots inserted (today: {today})")
    return inserted


# ─── Step 3: Spotify enrichment ─────────────────────────────────────────────

def run_enrich() -> int:
    """
    Enrich concerts with artist popularity.

    Spotify removed popularity/followers from their API in 2025, so we use
    face_value_to_pop_tier() as the primary source. Spotify is queried only
    for the artist URL (1 req/artist, deduplicated, with 429 backoff).
    All concerts get marked as enriched regardless of Spotify availability.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.source, c.source_event_id, c.artist,
               COALESCE(ps.min_price, 0) AS face_value
        FROM concerts c
        LEFT JOIN (
            SELECT source, source_event_id, MIN(min_price) AS min_price
            FROM price_snapshots
            WHERE min_price IS NOT NULL
            GROUP BY source, source_event_id
        ) ps ON ps.source = c.source AND ps.source_event_id = c.source_event_id
        WHERE c.spotify_popularity IS NULL AND c.artist IS NOT NULL
    """).fetchall()
    conn.close()

    if not rows:
        print("Enrichment: all concerts already enriched")
        return 0

    print(f"Enriching {len(rows)} concerts...")

    # Popularity tier derived from face value — no Spotify API call needed.
    # Spotify removed popularity/followers from their API in 2025, so the
    # face_value_to_pop_tier() heuristic is the authoritative source.
    enriched = 0
    for source, event_id, artist, face_value in rows:
        pop_tier = face_value_to_pop_tier(float(face_value) if face_value else None)
        update_spotify(source, event_id,
                       followers=None,
                       popularity=pop_tier,
                       url=None)
        enriched += 1

    print(f"  {enriched} concerts enriched (face-value popularity tiers)")
    return enriched


# ─── Main ────────────────────────────────────────────────────────────────────

def main(mode: str = "full"):
    init_db()
    start = datetime.now()
    print(f"\n=== Comanche Pipeline  [{start.strftime('%Y-%m-%d %H:%M')}]  mode={mode} ===")

    if mode in ("full", "discover"):
        run_discover()
    if mode in ("full", "snapshot"):
        run_snapshot()
    if mode in ("full", "enrich"):
        run_enrich()

    elapsed = (datetime.now() - start).seconds
    print(f"=== Done in {elapsed}s ===\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    main(mode)
