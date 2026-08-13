import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "inputs" / "data" / "comanche.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS concerts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source              TEXT NOT NULL,
            source_event_id     TEXT NOT NULL,
            name                TEXT,
            artist              TEXT,
            venue               TEXT,
            city                TEXT    DEFAULT 'New York',
            city_pop            INTEGER DEFAULT 8550971,
            country             TEXT    DEFAULT 'US',
            start_date          TEXT,
            start_time          TEXT,
            url                 TEXT,
            first_seen_date     TEXT,
            spotify_followers   INTEGER,
            spotify_popularity  REAL,
            spotify_url         TEXT,
            UNIQUE(source, source_event_id)
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            source              TEXT NOT NULL,
            source_event_id     TEXT NOT NULL,
            collection_date     TEXT NOT NULL,
            days_until          INTEGER,
            min_price           REAL,
            avg_price           REAL,
            listing_count       INTEGER,
            UNIQUE(source, source_event_id, collection_date)
        );

        CREATE INDEX IF NOT EXISTS idx_snap_event
            ON price_snapshots(source, source_event_id);
        CREATE INDEX IF NOT EXISTS idx_snap_date
            ON price_snapshots(collection_date);
    """)
    conn.commit()
    conn.close()
    print(f"DB ready: {DB_PATH}")


def upsert_concert(event: dict) -> bool:
    """Insert concert. Returns True if new row was created."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO concerts (
                source, source_event_id, name, artist, venue,
                city, city_pop, country, start_date, start_time,
                url, first_seen_date
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            event["source"],
            event["source_event_id"],
            event.get("name"),
            event.get("artist"),
            event.get("venue"),
            event.get("city", "New York"),
            event.get("city_pop", 8_550_971),
            event.get("country", "US"),
            event.get("start_date"),
            event.get("start_time"),
            event.get("url"),
            datetime.now(timezone.utc).date().isoformat(),
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def insert_snapshot(snap: dict) -> bool:
    """Insert one daily price row. Returns True if inserted (not duplicate)."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO price_snapshots (
                source, source_event_id, collection_date,
                days_until, min_price, avg_price, listing_count
            ) VALUES (?,?,?,?,?,?,?)
        """, (
            snap["source"],
            snap["source_event_id"],
            snap["collection_date"],
            snap.get("days_until"),
            snap.get("min_price"),
            snap.get("avg_price"),
            snap.get("listing_count"),
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_upcoming_concerts() -> list[dict]:
    conn = get_conn()
    today = datetime.now(timezone.utc).date().isoformat()
    rows = conn.execute("""
        SELECT source, source_event_id, artist, name, venue, start_date
        FROM concerts
        WHERE start_date >= ?
        ORDER BY start_date
    """, (today,)).fetchall()
    conn.close()
    cols = ["source", "source_event_id", "artist", "name", "venue", "start_date"]
    return [dict(zip(cols, r)) for r in rows]


def update_spotify(source: str, source_event_id: str,
                   followers: int, popularity: float, url: str):
    conn = get_conn()
    conn.execute("""
        UPDATE concerts
        SET spotify_followers=?, spotify_popularity=?, spotify_url=?
        WHERE source=? AND source_event_id=?
    """, (followers, popularity, url, source, source_event_id))
    conn.commit()
    conn.close()


def get_price_history(source: str, source_event_id: str) -> list[tuple]:
    """Returns rows (collection_date, days_until, min_price, avg_price) oldest-first."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT collection_date, days_until, min_price, avg_price
        FROM price_snapshots
        WHERE source=? AND source_event_id=?
        ORDER BY days_until DESC
    """, (source, source_event_id)).fetchall()
    conn.close()
    return rows


def get_all_snapshots_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT
            s.source, s.source_event_id,
            s.collection_date, s.days_until,
            s.min_price, s.avg_price, s.listing_count,
            c.artist, c.venue, c.start_date,
            c.spotify_popularity, c.spotify_followers, c.city_pop
        FROM price_snapshots s
        JOIN concerts c USING (source, source_event_id)
        WHERE s.min_price IS NOT NULL AND s.min_price > 0
        ORDER BY s.source_event_id, s.days_until DESC
    """, conn)
    conn.close()
    df["log_min_price"] = np.log(df["min_price"])
    df["log_avg_price"] = np.log(df["avg_price"].clip(lower=1))
    return df


if __name__ == "__main__":
    init_db()
