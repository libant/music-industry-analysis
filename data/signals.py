"""
Trading signals for NYC resale tickets.

Based on Haglund (2020) findings:
  - Prices peak ~60-90 days out, then drop toward concert
  - Probability of price change accelerates in final 20 days
  - NYC is the largest US market: highest starting prices + most volatility
  - Shape of price curve is similar across concerts; level varies by artist/venue

Signal logic:
  BUY  → 60-90 days out, price stabilized or trending up (brokers starting to buy)
  HOLD → 20-60 days out (peak demand window, hold for appreciation)
  SELL → 5-20 days out (prices drop as sellers panic before concert ends value)
  DUMP → <5 days (emergency sell — ticket becomes worthless at showtime)
  WATCH → >90 days (too early, gather data)

Usage:
    python3 signals.py                  # print all active signals
    python3 signals.py --json           # output as JSON
"""
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from db import get_price_history, get_conn


# ─── Signal parameters ───────────────────────────────────────────────────────

WATCH_THRESHOLD  = 90   # days: above this, just watch
BUY_OPEN         = 90   # days: earliest to buy
BUY_CLOSE        = 60   # days: buy decision deadline
HOLD_CLOSE       = 20   # days: start preparing to sell
DUMP_THRESHOLD   = 5    # days: emergency exit


def _trend(log_prices: list[float], window: int = 5) -> float:
    """Mean daily log-price change over last `window` observations."""
    if len(log_prices) < 2:
        return 0.0
    recent = log_prices[-window:]
    return float(np.mean(np.diff(recent))) if len(recent) >= 2 else 0.0


def price_signal(days_until: int, current_log_price: float,
                 history_log_prices: list[float]) -> dict:
    """
    Core signal logic for a single ticket.

    Parameters
    ----------
    days_until : days remaining until the concert
    current_log_price : log of today's min_price
    history_log_prices : list of log prices sorted oldest-first

    Returns
    -------
    dict with keys: signal, confidence, reason
    """
    trend = _trend(history_log_prices)
    n_obs = len(history_log_prices)

    if days_until > WATCH_THRESHOLD:
        return {
            "signal": "WATCH",
            "confidence": 0.30,
            "reason": f"{days_until}d out — too early. Monitor for price movements.",
        }

    if HOLD_CLOSE < days_until <= WATCH_THRESHOLD:
        # Buy window: 20-90 days out
        if days_until > BUY_CLOSE:
            # 60-90d: optimal buy zone
            if trend > 0.005:
                conf = min(0.85, 0.65 + trend * 20)
                return {
                    "signal": "BUY",
                    "confidence": round(conf, 2),
                    "reason": (f"Price rising ({trend:+.3f}/day) with {days_until}d out — "
                               "buy before further appreciation."),
                }
            elif n_obs >= 5 and trend > -0.003:
                return {
                    "signal": "BUY",
                    "confidence": 0.65,
                    "reason": f"Price stable in primary buy window ({days_until}d out).",
                }
            else:
                return {
                    "signal": "WATCH",
                    "confidence": 0.45,
                    "reason": (f"Price still falling ({trend:+.3f}/day). "
                               f"Wait for bottom before buying ({days_until}d out)."),
                }
        else:
            # 20-60d: hold zone, price should be rising toward peak
            return {
                "signal": "HOLD",
                "confidence": 0.60,
                "reason": (f"Peak demand window ({days_until}d out). "
                           "Hold — prices typically rise toward 20d mark."),
            }

    if DUMP_THRESHOLD < days_until <= HOLD_CLOSE:
        # Sell window: 5-20 days
        if trend < -0.01:
            conf = min(0.92, 0.75 + abs(trend) * 10)
            return {
                "signal": "SELL",
                "confidence": round(conf, 2),
                "reason": (f"Prices dropping fast ({trend:+.3f}/day) with {days_until}d "
                           "left — sell now before further decline."),
            }
        return {
            "signal": "SELL",
            "confidence": 0.70,
            "reason": (f"In sell window ({days_until}d out). "
                       "Prices drop ~60d→0d. Exit to capture value."),
        }

    # ≤5 days: emergency
    return {
        "signal": "DUMP",
        "confidence": 0.95,
        "reason": (f"URGENT — {days_until}d remaining. "
                   "Ticket value → 0 at showtime. Sell immediately."),
    }


# ─── Generate signals for all tracked events ─────────────────────────────────

def generate_signals() -> pd.DataFrame:
    conn = get_conn()
    latest = pd.read_sql_query("""
        SELECT
            s.source, s.source_event_id,
            s.days_until, s.min_price, s.avg_price,
            s.listing_count, s.collection_date,
            c.artist, c.name AS event_name, c.venue, c.start_date,
            c.spotify_popularity, c.spotify_followers
        FROM price_snapshots s
        JOIN concerts c USING (source, source_event_id)
        WHERE s.collection_date = (
            SELECT MAX(s2.collection_date)
            FROM price_snapshots s2
            WHERE s2.source = s.source
              AND s2.source_event_id = s.source_event_id
        )
          AND s.min_price IS NOT NULL
          AND s.days_until >= 0
        ORDER BY s.days_until
    """, conn)
    conn.close()

    if latest.empty:
        return pd.DataFrame()

    rows = []
    for _, ev in latest.iterrows():
        history = get_price_history(ev["source"], ev["source_event_id"])
        log_hist = [np.log(h[2]) for h in history if h[2] and h[2] > 0]
        current_log = np.log(max(ev["min_price"], 1))

        sig = price_signal(ev["days_until"], current_log, log_hist)

        rows.append({
            "artist":        ev["artist"] or ev["event_name"],
            "venue":         ev["venue"],
            "concert_date":  ev["start_date"],
            "days_until":    int(ev["days_until"]),
            "min_price":     ev["min_price"],
            "avg_price":     ev["avg_price"],
            "listings":      ev["listing_count"],
            "signal":        sig["signal"],
            "confidence":    sig["confidence"],
            "reason":        sig["reason"],
            "n_obs":         len(log_hist),
            "source_event_id": ev["source_event_id"],
        })

    return pd.DataFrame(rows)


# ─── Display ─────────────────────────────────────────────────────────────────

_ICONS = {
    "BUY":   "🟢 BUY ",
    "SELL":  "🔴 SELL",
    "DUMP":  "🚨 DUMP",
    "HOLD":  "🟡 HOLD",
    "WATCH": "⚪ WTCH",
}


def print_signals(df: pd.DataFrame):
    if df.empty:
        print("No price data yet. Run:  python3 pipeline.py")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    print()
    print("=" * 90)
    print(f"  COMANCHE TRADING SIGNALS — NYC          {today}")
    print("=" * 90)
    print(f"  {'SIGNAL':<7}  {'ARTIST':<28}  {'DATE':<10}  {'D':<4}  "
          f"{'MIN $':>7}  {'AVG $':>7}  {'CONF':>5}  REASON")
    print("-" * 90)

    for _, r in df.iterrows():
        icon = _ICONS.get(r["signal"], "     ")
        avg  = f"${r['avg_price']:6.0f}" if r["avg_price"] else "      -"
        print(f"  {icon}  {str(r['artist'])[:28]:<28}  {r['concert_date']}  "
              f"{r['days_until']:>3}d  ${r['min_price']:6.0f}  {avg}  "
              f"{r['confidence']:>4.0%}  {r['reason'][:45]}")

    print("=" * 90)
    counts = df["signal"].value_counts()
    summary = "  " + "  ".join(f"{s}: {counts.get(s,0)}" for s in ["BUY","SELL","DUMP","HOLD","WATCH"])
    print(summary)
    print()


# ─── Backtest (once data accumulates) ────────────────────────────────────────

def backtest(min_history_days: int = 30) -> pd.DataFrame:
    """
    Simulate: buy at day 90, sell at day 20. Measure profit.
    Requires events with ≥ min_history_days of snapshots.
    """
    from db import get_all_snapshots_df
    df = get_all_snapshots_df()

    results = []
    for event_id, grp in df.groupby("source_event_id"):
        grp = grp.sort_values("days_until", ascending=False)
        if len(grp) < min_history_days:
            continue

        buy_row  = grp[grp["days_until"].between(85, 95)].head(1)
        sell_row = grp[grp["days_until"].between(18, 25)].head(1)

        if buy_row.empty or sell_row.empty:
            continue

        buy_price  = buy_row["min_price"].values[0]
        sell_price = sell_row["min_price"].values[0]
        profit_pct = (sell_price - buy_price) / buy_price * 100

        results.append({
            "artist":      grp["artist"].iloc[0],
            "venue":       grp["venue"].iloc[0],
            "concert_date": grp["start_date"].iloc[0],
            "buy_price":   round(buy_price, 2),
            "sell_price":  round(sell_price, 2),
            "profit_pct":  round(profit_pct, 1),
            "profitable":  profit_pct > 0,
        })

    if not results:
        print(f"Not enough data yet for backtest. Need events with {min_history_days}+ days of history.")
        return pd.DataFrame()

    bt = pd.DataFrame(results).sort_values("profit_pct", ascending=False)
    win_rate = bt["profitable"].mean()
    avg_profit = bt["profit_pct"].mean()
    print(f"\nBacktest: buy@90d / sell@20d  —  {len(bt)} events")
    print(f"  Win rate: {win_rate:.0%}   Avg profit: {avg_profit:+.1f}%")
    print(bt[["artist", "concert_date", "buy_price", "sell_price", "profit_pct"]].to_string(index=False))
    return bt


if __name__ == "__main__":
    df = generate_signals()
    if "--json" in sys.argv:
        print(json.dumps(df.to_dict(orient="records"), indent=2, default=str))
    elif "--backtest" in sys.argv:
        backtest()
    else:
        print_signals(df)
