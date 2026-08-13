"""
Simulate a synthetic concert price dataset for testing the analysis pipeline.

Generates fake events and daily price snapshots that match the schema of
inputs/data/comanche.db without touching the real database. Useful for
running 03-analysis.py and 04-generate_report.py on a clean machine before
real data is collected.

Output: inputs/data/simulated.db

Usage:
    python3 scripts/00-simulate_data.py
"""

import sqlite3
import numpy as np
import random
from pathlib import Path
from datetime import date, timedelta

RANDOM_SEED = 42
N_ARTISTS   = 20
N_EVENTS    = 60
N_DAYS      = 41   # matches real collection window
OUT_DB      = Path(__file__).parent.parent / "inputs" / "data" / "simulated.db"

np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

ARTISTS = [f"Artist_{i:02d}" for i in range(N_ARTISTS)]
VENUES  = ["Madison Square Garden", "Barclays Center", "Brooklyn Steel",
           "Irving Plaza", "Bowery Ballroom", "Music Hall of Williamsburg"]
POP_TIERS = {30: (20, 50), 50: (50, 100), 65: (100, 200)}


def make_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        DROP TABLE IF EXISTS price_snapshots;
        DROP TABLE IF EXISTS concerts;

        CREATE TABLE concerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL, source_event_id TEXT NOT NULL,
            name TEXT, artist TEXT, venue TEXT,
            city TEXT DEFAULT 'New York', city_pop INTEGER DEFAULT 8550971,
            country TEXT DEFAULT 'US', start_date TEXT,
            start_time TEXT, url TEXT, first_seen_date TEXT,
            spotify_followers INTEGER, spotify_popularity REAL, spotify_url TEXT,
            UNIQUE(source, source_event_id)
        );

        CREATE TABLE price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL, source_event_id TEXT NOT NULL,
            collection_date TEXT NOT NULL, days_until INTEGER,
            min_price REAL, avg_price REAL, listing_count INTEGER,
            UNIQUE(source, source_event_id, collection_date)
        );
    """)
    conn.commit()
    return conn


def main():
    conn = make_db(OUT_DB)
    start_date = date(2026, 6, 10)

    events = []
    for i in range(N_EVENTS):
        artist = random.choice(ARTISTS)
        tier   = random.choice([30, 50, 65])
        lo, hi = POP_TIERS[tier]
        base_price = np.random.uniform(lo, hi)
        event_date = start_date + timedelta(days=random.randint(5, 120))
        eid = f"sim_{i:04d}"

        conn.execute("""
            INSERT OR IGNORE INTO concerts
            (source, source_event_id, name, artist, venue, start_date,
             first_seen_date, spotify_popularity)
            VALUES (?,?,?,?,?,?,?,?)
        """, ("simulated", eid, f"{artist} at {random.choice(VENUES)}",
              artist, random.choice(VENUES),
              event_date.isoformat(), start_date.isoformat(), tier))
        events.append((eid, event_date, base_price))

    # Daily snapshots over the collection window
    for day_offset in range(N_DAYS):
        collection = start_date + timedelta(days=day_offset)
        for eid, event_date, base_price in events:
            days_until = (event_date - collection).days
            if days_until < 0:
                continue
            # Slight random walk on price; generally flat with small noise
            noise = np.random.normal(0, base_price * 0.02)
            price = max(5.0, base_price + noise)
            conn.execute("""
                INSERT OR IGNORE INTO price_snapshots
                (source, source_event_id, collection_date, days_until,
                 min_price, avg_price, listing_count)
                VALUES (?,?,?,?,?,?,?)
            """, ("simulated", eid, collection.isoformat(), days_until,
                  round(price, 2), round(price * 1.1, 2), random.randint(1, 50)))

    conn.commit()
    conn.close()

    total = N_EVENTS * N_DAYS
    print(f"Simulated DB written to: {OUT_DB}")
    print(f"  {N_EVENTS} events | {N_ARTISTS} artists | up to {total} snapshots")


if __name__ == "__main__":
    main()
