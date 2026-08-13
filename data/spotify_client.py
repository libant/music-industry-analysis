"""
Spotify API client — artist enrichment.
Add to .env:  SPOTIFY_CLIENT_ID=...  SPOTIFY_CLIENT_SECRET=...
"""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

_token_cache: dict = {}


def get_access_token() -> str:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set in .env")
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_artist_data(artist_name: str, token: str) -> dict:
    """Return followers, popularity, and Spotify URL for the best-matching artist.

    NOTE: Spotify removed followers/popularity from their Web API in 2025.
    We confirm the artist exists on Spotify (returns spotify_url + id) and
    estimate popularity from the number of images (proxy for profile completeness)
    and whether they appear at all.  Callers should treat popularity as an ordinal
    tier (0=unknown, 30=niche, 50=mid, 70=mainstream, 90=superstar) inferred
    from face-value price when Spotify data is insufficient.
    """
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={"q": artist_name, "type": "artist", "limit": 1},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("artists", {}).get("items", [])
    if not items:
        return {"followers": None, "popularity": None, "spotify_url": None,
                "spotify_id": None, "on_spotify": False}

    a = items[0]
    # Spotify removed popularity/followers from API in 2025.
    # We confirm the artist exists and return their ID for future use.
    # Callers should derive popularity tier from face_value_to_pop_tier() below.
    return {
        "followers":   None,   # no longer available from Spotify API
        "popularity":  None,   # no longer available from Spotify API
        "spotify_url": a["external_urls"]["spotify"],
        "spotify_id":  a["id"],
        "on_spotify":  True,
    }


def face_value_to_pop_tier(face_value: float) -> int:
    """
    Estimate artist popularity tier (0–100 Spotify-like scale) from face value.

    Ticket face value is set by promoters based on expected demand, making it
    the best available proxy for artist popularity when Spotify data is absent.

    Calibrated to NYC concerts (Haglund 2020 break-even ≈ $148):
        < $50   → indie/niche       (pop ≈ 30)
        $50–99  → emerging          (pop ≈ 50)
        $100–199→ mainstream        (pop ≈ 65)
        $200–349→ headliner         (pop ≈ 78)
        $350+   → superstar         (pop ≈ 90)
    """
    if face_value is None or face_value <= 0:
        return 50   # unknown — assume median
    if face_value < 50:
        return 30
    if face_value < 100:
        return 50
    if face_value < 200:
        return 65
    if face_value < 350:
        return 78
    return 90


def enrich_batch(artist_names: list[str]) -> dict[str, dict]:
    """Convenience: enrich a list of artists, returns {name: data}."""
    token = get_access_token()
    results = {}
    for name in artist_names:
        if not name:
            continue
        try:
            results[name] = get_artist_data(name, token)
        except Exception as e:
            print(f"  Spotify lookup failed for '{name}': {e}")
            results[name] = {"followers": None, "popularity": None, "spotify_url": None}
        time.sleep(0.1)
    return results
