"""
Replicates Haglund (2020) analysis on NYC Ticketmaster data.

Sections:
  1. EDA  — price distributions, price-over-time curves
  2. Models — Linear Reg → Polynomial → Random Forest → MLP
  3. Report — summary statistics table matching paper format

Requires ≥ 30 days of daily snapshots. Run 01-gather_data.py daily first.

Usage:
    python3 scripts/03-analysis.py          # full analysis + plots
    python3 scripts/03-analysis.py eda      # EDA only
    python3 scripts/03-analysis.py models   # models only
"""
import sys
import os
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures, MinMaxScaler
from sklearn.metrics import mean_squared_error

warnings.filterwarnings("ignore")

from db import get_all_snapshots_df

PLOT_DIR = str(Path(__file__).parent.parent / "outputs" / "figures")
os.makedirs(PLOT_DIR, exist_ok=True)


# ─── Data loading ────────────────────────────────────────────────────────────

def load_data(min_obs: int = 7) -> pd.DataFrame:
    df = get_all_snapshots_df()
    if df.empty:
        print("No data yet — run pipeline.py first.")
        return df

    counts = df.groupby("source_event_id")["collection_date"].count()
    valid  = counts[counts >= min_obs].index
    df = df[df["source_event_id"].isin(valid)].copy()
    print(f"Loaded {len(df):,} snapshots | {df['source_event_id'].nunique()} events "
          f"| {df['artist'].nunique()} artists | days_until range: "
          f"{int(df['days_until'].min())}–{int(df['days_until'].max())}")
    return df


# ─── EDA ─────────────────────────────────────────────────────────────────────

def plot_price_distribution(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(df["min_price"].clip(0, 2000), bins=60, color="#4472C4", edgecolor="white")
    axes[0].set_title("Ticket Price Distribution (NYC)")
    axes[0].set_xlabel("Price ($)")
    axes[0].set_ylabel("Count")

    axes[1].hist(df["log_min_price"], bins=60, color="#4472C4", edgecolor="white")
    axes[1].set_title("Log Ticket Price Distribution (NYC)")
    axes[1].set_xlabel("log(Price)")
    axes[1].set_ylabel("Count")

    fig.suptitle("Figure 1 — Price Distributions", fontsize=12, y=1.01)
    plt.tight_layout()
    path = f"{PLOT_DIR}/01_price_distribution.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def plot_mean_price_over_time(df: pd.DataFrame):
    mean_by_day = (df[df["days_until"] <= 150]
                   .groupby("days_until")["log_min_price"].mean())

    plt.figure(figsize=(10, 5))
    plt.plot(mean_by_day.index, mean_by_day.values, linewidth=1.5, color="#4472C4")
    plt.gca().invert_xaxis()
    plt.xlabel("Days Until Concert")
    plt.ylabel("Mean Log Price")
    plt.title("Figure 2 — Mean Log Ticket Price Over Time (NYC)")
    plt.axvline(60, color="orange", linestyle="--", alpha=0.6, label="60d mark")
    plt.axvline(20, color="red",    linestyle="--", alpha=0.6, label="20d mark")
    plt.legend()
    plt.tight_layout()
    path = f"{PLOT_DIR}/02_mean_price_over_time.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_price_by_artist(df: pd.DataFrame, top_n: int = 12):
    top = (df.groupby("artist")["source_event_id"].nunique()
           .nlargest(top_n).index)
    sub = df[df["artist"].isin(top) & (df["days_until"] <= 150)]

    plt.figure(figsize=(13, 6))
    for artist, grp in sub.groupby("artist"):
        m = grp.groupby("days_until")["log_min_price"].mean()
        plt.plot(m.index, m.values, label=artist, alpha=0.85)
    plt.gca().invert_xaxis()
    plt.xlabel("Days Until Concert")
    plt.ylabel("Mean Log Price")
    plt.title(f"Figure 3 — Log Price Over Time by Artist (NYC, top {top_n})")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    path = f"{PLOT_DIR}/03_price_by_artist.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def plot_price_boxplot_by_artist(df: pd.DataFrame, top_n: int = 20):
    top = (df.groupby("artist")["log_min_price"].median()
           .nlargest(top_n).index)
    sub = df[df["artist"].isin(top)]

    order = (sub.groupby("artist")["log_min_price"].median()
             .sort_values().index.tolist())
    groups = [sub[sub["artist"] == a]["log_min_price"].values for a in order]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.boxplot(groups, tick_labels=order, vert=True, patch_artist=True,
               flierprops=dict(marker="D", markersize=3, alpha=0.4))
    ax.set_xticklabels(order, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Log Price")
    ax.set_title("Figure 4 — Artist Log Ticket Price Boxplot (NYC)")
    plt.tight_layout()
    path = f"{PLOT_DIR}/04_price_boxplot_artists.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")


def run_eda(df: pd.DataFrame):
    print("\n=== EDA ===")
    print(df[["min_price", "log_min_price", "days_until", "listing_count"]].describe().round(3))
    plot_price_distribution(df)
    plot_mean_price_over_time(df)
    plot_price_by_artist(df)
    plot_price_boxplot_by_artist(df)


# ─── Models ──────────────────────────────────────────────────────────────────

def _rolling_eval(X, y, n_folds: int = 5):
    """Time-series walk-forward eval: train on first half, test on rolling fifths."""
    split = len(X) // 2
    rmses, maes = [], []
    fold_size = (len(X) - split) // n_folds

    for fold in range(n_folds):
        train_end = split + fold * fold_size
        test_end  = train_end + fold_size
        if test_end > len(X):
            break
        yield X[:train_end], y[:train_end], X[train_end:test_end], y[train_end:test_end]


def _score(y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = np.mean(np.abs(y_true - y_pred))
    return rmse, mae


def model_baseline(df: pd.DataFrame) -> tuple:
    """OLS: days_until → log_min_price."""
    data = df[["days_until", "log_min_price"]].dropna().sort_values("days_until")
    X = data[["days_until"]].values
    y = data["log_min_price"].values
    split = len(X) // 2
    m = LinearRegression().fit(X[:split], y[:split])
    rmse, mae = _score(y[split:], m.predict(X[split:]))
    print(f"  Baseline Linear             RMSE={rmse:.3f}  MAE={mae:.3f}")
    return m, rmse, mae


def model_polynomial(df: pd.DataFrame, degree: int = 3) -> tuple:
    """Polynomial (degree=3) OLS on days_until."""
    data = df[["days_until", "log_min_price"]].dropna().sort_values("days_until")
    poly = PolynomialFeatures(degree=degree, include_bias=False)
    X = poly.fit_transform(data[["days_until"]].values)
    y = data["log_min_price"].values
    split = len(X) // 2
    m = LinearRegression().fit(X[:split], y[:split])
    rmse, mae = _score(y[split:], m.predict(X[split:]))
    print(f"  Polynomial (d={degree})           RMSE={rmse:.3f}  MAE={mae:.3f}")
    return m, poly, rmse, mae


def model_random_forest(df: pd.DataFrame) -> tuple:
    """RF with days_until, spotify_popularity, spotify_followers, city_pop."""
    feats = ["days_until", "spotify_popularity", "spotify_followers", "city_pop"]
    avail = [f for f in feats if f in df.columns and df[f].notna().sum() > 100]
    data  = df[avail + ["log_min_price"]].dropna().sort_values("days_until")

    X = data[avail].values
    y = data["log_min_price"].values
    split = len(X) // 2

    m = RandomForestRegressor(n_estimators=200, max_features="sqrt",
                              n_jobs=-1, random_state=42)
    m.fit(X[:split], y[:split])
    rmse, mae = _score(y[split:], m.predict(X[split:]))
    print(f"  Random Forest               RMSE={rmse:.3f}  MAE={mae:.3f}")

    imp = pd.Series(m.feature_importances_, index=avail).sort_values(ascending=False)
    print("    Feature importances:", dict(imp.round(3)))
    return m, avail, rmse, mae


def model_lstm(df: pd.DataFrame) -> tuple:
    """MLP neural network as LSTM substitute (TF/PyTorch unsupported on Python 3.13).

    Uses sliding-window features on the mean log-price time series, matching
    the spirit of the paper's LSTM while staying within available dependencies.
    """
    from sklearn.neural_network import MLPRegressor

    series = (df[df["days_until"] <= 150]
              .groupby("days_until")["log_min_price"]
              .mean()
              .sort_index(ascending=False)
              .values)

    if len(series) < 30:
        print(f"  MLP-NN: need ≥30 data points, have {len(series)}.")
        return None, None, None, None

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(series.reshape(-1, 1)).flatten()

    SEQ = min(10, len(scaled) // 4)
    Xs, ys = [], []
    for i in range(SEQ, len(scaled)):
        Xs.append(scaled[i - SEQ:i])
        ys.append(scaled[i])
    Xs, ys = np.array(Xs), np.array(ys)

    split = int(len(Xs) * 0.7)

    model = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=500,
                         random_state=42, early_stopping=True)
    model.fit(Xs[:split], ys[:split])

    preds   = scaler.inverse_transform(model.predict(Xs[split:]).reshape(-1, 1)).flatten()
    actuals = scaler.inverse_transform(ys[split:].reshape(-1, 1)).flatten()
    rmse, mae = _score(actuals, preds)
    print(f"  MLP Neural Net (seq={SEQ})    RMSE={rmse:.3f}  MAE={mae:.3f}")

    plt.figure(figsize=(10, 4))
    plt.plot(actuals, label="Actual", linewidth=1.5)
    plt.plot(preds,   label="Prediction", linewidth=1.5, linestyle="--")
    plt.xlabel("Time step")
    plt.ylabel("Log Price")
    plt.title("Figure 5 — MLP Neural Net: Predicted vs Actual Log Price (NYC mean)")
    plt.legend()
    plt.tight_layout()
    path = f"{PLOT_DIR}/05_mlp_prediction.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved: {path}")

    return model, scaler, rmse, mae


def run_models(df: pd.DataFrame):
    print("\n=== Model Performance (target: log_min_price) ===")
    print(f"  {'Model':<30} {'RMSE':>6}  {'MAE':>6}")
    print("  " + "-" * 45)
    model_baseline(df)
    model_polynomial(df)
    model_random_forest(df)
    model_lstm(df)


# ─── Summary stats table ─────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame):
    print("\n=== Summary Statistics ===")
    stats = df.groupby("artist").agg(
        events   = ("source_event_id", "nunique"),
        obs      = ("log_min_price", "count"),
        mean_log = ("log_min_price", "mean"),
        std_log  = ("log_min_price", "std"),
        mean_raw = ("min_price", "mean"),
    ).round(3).sort_values("mean_log", ascending=False)
    print(stats.head(20).to_string())


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    df   = load_data()

    if df.empty:
        sys.exit(0)

    if mode in ("full", "eda"):
        run_eda(df)
    if mode in ("full", "models"):
        run_models(df)
    if mode == "full":
        print_summary(df)

    print("\nAll outputs saved to:", PLOT_DIR)
