"""
Parametric model from Haglund (2020) — "What Makes The Market Tix"

Uses the MLE parameters from Tables 5.2.5–5.2.7 to estimate:
  - Expected secondary market (resale) price at any days_until
  - Expected price trajectory from purchase to concert date
  - Estimated profit given a face-value purchase price

Key parameters (from full artist-level model, Table 5.2.5, Model 12):
  γ₀ = 5.153   (baseline starting log-price)
  γ₁ = -0.0002 (days_until effect on starting price)
  γ₂ = 0.004   (log_city_pop effect on starting price)
  a₀ = -0.008  (baseline mean daily log-price change)
  a₁ = 0.0002  (days_until effect on price change — positive = bigger changes early)
  a₂ = 0.0005  (log_city_pop effect on price change)
  σ₀ = 1.268   (std dev of starting price)
  σ_ε = 0.094  (std dev of daily price changes)
  β₀ = -1.752  (logit intercept for price change probability)
  β₁ = -0.020  (days_until effect on change probability — negative = more changes near date)
  β₂ = 0.052   (log_city_pop effect on change probability)

NYC constants:
  city_pop = 8,550,971  →  log_city_pop ≈ 15.96
  (NYC is rank 1 in Table 5.2.6 with μ₀=5.149, μ_ε=0.0047, p=0.052)

Interpretation:
  - starting_price: what a resale ticket costs the moment it hits the secondary market
  - price_change:   how much it moves per day (positive early, negative near concert)
  - change_prob:    probability any given ticket changes price that day

Usage:
    from haglund_model import estimate_resale_price, estimate_profit, simulate_trajectory
"""
import numpy as np
from scipy.special import expit   # logistic / sigmoid function

# ─── MLE parameters from Table 5.2.5 (Model 12 — full dataset) ──────────────

GAMMA_0 = 5.153     # baseline log starting price
GAMMA_1 = -0.0002   # days_until slope on starting price
GAMMA_2 = 0.001     # log_city_pop slope on starting price (Model 12 value)

A_0 = -0.008        # baseline mean log price change per day
A_1 = 0.0002        # days_until slope on price change
A_2 = 0.0006        # log_city_pop slope on price change (using Model 11 value)

SIGMA_0   = 1.268   # std of starting log price (between-concert variation)
SIGMA_EPS = 0.094   # std of daily log price changes

BETA_0 = -1.752     # logit intercept for change probability
BETA_1 = -0.020     # days_until slope (negative → higher prob near concert)
BETA_2 = 0.052      # log_city_pop slope

# NYC fixed
NYC_POP     = 8_550_971
LOG_NYC_POP = np.log(NYC_POP)     # ≈ 15.96


def _normalize_pop(spotify_popularity: float | None) -> float:
    """Normalize Spotify popularity (0–100) to 0–1 scale."""
    if spotify_popularity is None:
        return 0.5   # assume median if unknown
    return float(spotify_popularity) / 100.0


def expected_starting_log_price(days_until: int,
                                 spotify_popularity: float | None = None) -> float:
    """
    Expected log-price of a resale ticket entering the market `days_until` days
    before the concert.

    μ₀ = γ₀ + γ₁·days_until + γ₂·log_city_pop
    (artist_pop effect on starting price was not significant in the paper)
    """
    return GAMMA_0 + GAMMA_1 * days_until + GAMMA_2 * LOG_NYC_POP


def expected_daily_log_change(days_until: int,
                               spotify_popularity: float | None = None) -> float:
    """
    Expected mean daily log-price change for a ticket with `days_until` days remaining.

    μ_ε = a₀ + a₁·days_until + a₂·log_city_pop
    Positive early (far from concert) → negative as concert approaches.
    """
    pop  = _normalize_pop(spotify_popularity)
    return A_0 + A_1 * days_until + A_2 * LOG_NYC_POP


def change_probability(days_until: int,
                        spotify_popularity: float | None = None) -> float:
    """
    Probability that a given ticket changes price on any given day.

    p = sigmoid(β₀ + β₁·days_until + β₂·log_city_pop)
    Increases as concert approaches.
    """
    pop   = _normalize_pop(spotify_popularity)
    logit = BETA_0 + BETA_1 * days_until + BETA_2 * LOG_NYC_POP
    return float(expit(logit))


def estimate_resale_price(days_until: int,
                           spotify_popularity: float | None = None) -> float:
    """
    Point estimate of expected resale price (in $) for a ticket
    `days_until` days before the concert.
    """
    log_p = expected_starting_log_price(days_until, spotify_popularity)
    # Accumulate expected price changes from the starting day back to this day.
    # This is a simplified path-integral — for a quick estimate we just use
    # the mean starting price at this days_until value.
    return float(np.exp(log_p))


def simulate_trajectory(days_until_start: int = 120,
                         spotify_popularity: float | None = None,
                         n_paths: int = 200,
                         seed: int = 42) -> dict:
    """
    Simulate N price paths from `days_until_start` down to 0.

    Returns:
        days:        array of days_until (high → low, i.e., old → recent)
        mean_price:  mean simulated price path
        p5, p95:     5th and 95th percentiles
        peak_day:    estimated optimal sell day (max of mean path)
    """
    rng  = np.random.default_rng(seed)
    days = np.arange(days_until_start, -1, -1)
    n    = len(days)

    # Starting log prices for each path
    mu_start = expected_starting_log_price(days_until_start, spotify_popularity)
    log_prices = rng.normal(loc=mu_start, scale=SIGMA_0 * 0.3, size=(n_paths,))

    paths = np.zeros((n_paths, n))
    paths[:, 0] = log_prices

    for t, d in enumerate(days[1:], start=1):
        mu_change = expected_daily_log_change(d, spotify_popularity)
        changed   = rng.random(n_paths) < change_probability(d, spotify_popularity)
        delta     = rng.normal(loc=mu_change, scale=SIGMA_EPS, size=n_paths)
        paths[:, t] = paths[:, t-1] + delta * changed

    prices      = np.exp(paths)
    mean_prices = prices.mean(axis=0)
    peak_idx    = np.argmax(mean_prices)

    return {
        "days":       days,
        "mean_price": mean_prices,
        "p25":        np.percentile(prices, 25, axis=0),
        "p75":        np.percentile(prices, 75, axis=0),
        "p5":         np.percentile(prices,  5, axis=0),
        "p95":        np.percentile(prices, 95, axis=0),
        "peak_day":   int(days[peak_idx]),
        "peak_price": float(mean_prices[peak_idx]),
        "final_price": float(mean_prices[-1]),
    }


def estimate_profit(face_value: float,
                    buy_days_until: int,
                    sell_days_until: int,
                    spotify_popularity: float | None = None,
                    platform_fee_pct: float = 0.15) -> dict:
    """
    Estimate profit from buying one ticket at face_value with `buy_days_until`
    days to go and selling on the resale market at `sell_days_until` days to go.

    platform_fee_pct: typical resale platform fee (15% default for StubHub/TM).

    Returns a dict with estimated financials.
    """
    traj = simulate_trajectory(
        days_until_start=buy_days_until,
        spotify_popularity=spotify_popularity,
    )

    # Find expected sell price at sell_days_until
    sell_idx   = np.searchsorted(-traj["days"], -sell_days_until)
    sell_idx   = min(sell_idx, len(traj["days"]) - 1)
    sell_price = float(traj["mean_price"][sell_idx])
    sell_p25   = float(traj["p25"][sell_idx])
    sell_p75   = float(traj["p75"][sell_idx])

    net_proceeds = sell_price * (1 - platform_fee_pct)
    profit       = net_proceeds - face_value
    roi          = profit / face_value * 100 if face_value > 0 else 0

    return {
        "face_value":        round(face_value, 2),
        "buy_days_until":    buy_days_until,
        "sell_days_until":   sell_days_until,
        "est_sell_price":    round(sell_price, 2),
        "sell_price_p25":    round(sell_p25, 2),
        "sell_price_p75":    round(sell_p75, 2),
        "platform_fee":      round(sell_price * platform_fee_pct, 2),
        "net_proceeds":      round(net_proceeds, 2),
        "estimated_profit":  round(profit, 2),
        "roi_pct":           round(roi, 1),
        "peak_sell_day":     traj["peak_day"],
        "peak_sell_price":   round(traj["peak_price"], 2),
        "signal":            "BUY" if roi > 20 else ("WATCH" if roi > 5 else "SKIP"),
    }


def score_event(face_value: float,
                days_until: int,
                spotify_popularity: float | None = None) -> dict:
    """
    Quick-score an event for trading potential.
    Uses optimal sell timing (peak_day from simulation).
    """
    traj = simulate_trajectory(
        days_until_start=days_until,
        spotify_popularity=spotify_popularity,
    )
    optimal_sell = traj["peak_day"]
    return estimate_profit(
        face_value=face_value,
        buy_days_until=days_until,
        sell_days_until=optimal_sell,
        spotify_popularity=spotify_popularity,
    )


if __name__ == "__main__":
    # Demo: price of face-value $75 ticket 90 days out, Spotify pop=75
    print("=== Haglund Parametric Model — NYC ===\n")

    for pop, label in [(90, "Superstar (pop=90)"), (65, "Mid-tier (pop=65)"), (40, "Indie (pop=40)")]:
        r = estimate_profit(face_value=75, buy_days_until=90,
                            sell_days_until=20, spotify_popularity=pop)
        print(f"{label}:")
        print(f"  Buy at: ${r['face_value']} (90d out)")
        print(f"  Est. sell (20d): ${r['est_sell_price']}  [{r['sell_price_p25']}-{r['sell_price_p75']}]")
        print(f"  Net profit: ${r['estimated_profit']}  ROI: {r['roi_pct']}%")
        print(f"  Optimal sell: {r['peak_sell_day']}d out @ ${r['peak_sell_price']}")
        print(f"  Signal: {r['signal']}")
        print()
