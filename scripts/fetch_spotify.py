#!/usr/bin/env python3
"""
Fetch Spotify top tracks and artists, write to _data/spotify.yml.

Requires SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REFRESH_TOKEN
as environment variables (stored as GitHub Secrets).

Usage:
    python scripts/fetch_spotify.py

Dependencies:
    pip install requests pyyaml
"""

import os
import sys
from pathlib import Path

DATA_DIR = Path("_data")


def get_access_token():
    import requests
    import base64

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        print("  ERROR: Missing SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, or SPOTIFY_REFRESH_TOKEN")
        return None

    auth_str = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_str}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        print(f"  ERROR: Could not refresh Spotify token — {e}")
        return None


def fetch_top_tracks(token, limit=20, time_range="medium_term"):
    import requests

    try:
        r = requests.get(
            "https://api.spotify.com/v1/me/top/tracks",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": limit, "time_range": time_range},
            timeout=15,
        )
        r.raise_for_status()
        tracks = []
        for t in r.json().get("items", []):
            album_images = t.get("album", {}).get("images", [])
            tracks.append({
                "name": t["name"],
                "artist": ", ".join(a["name"] for a in t.get("artists", [])),
                "album": t.get("album", {}).get("name", ""),
                "album_image": album_images[1]["url"] if len(album_images) > 1 else (album_images[0]["url"] if album_images else ""),
                "url": t.get("external_urls", {}).get("spotify", ""),
            })
        return tracks
    except Exception as e:
        print(f"  ERROR fetching top tracks: {e}")
        return []


def fetch_top_artists(token, limit=12, time_range="medium_term"):
    import requests

    try:
        r = requests.get(
            "https://api.spotify.com/v1/me/top/artists",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": limit, "time_range": time_range},
            timeout=15,
        )
        r.raise_for_status()
        artists = []
        for a in r.json().get("items", []):
            images = a.get("images", [])
            artists.append({
                "name": a["name"],
                "genres": a.get("genres", [])[:3],
                "image": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else ""),
                "url": a.get("external_urls", {}).get("spotify", ""),
            })
        return artists
    except Exception as e:
        print(f"  ERROR fetching top artists: {e}")
        return []


def write_yaml(data):
    import yaml

    DATA_DIR.mkdir(exist_ok=True)
    outpath = DATA_DIR / "spotify.yml"

    with open(outpath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  Wrote data to {outpath}")


if __name__ == "__main__":
    print("\n── Spotify ──")
    token = get_access_token()
    if not token:
        print("  Skipping Spotify (no credentials).")
        sys.exit(0)

    tracks = fetch_top_tracks(token)
    artists = fetch_top_artists(token)

    print(f"  Fetched {len(tracks)} tracks, {len(artists)} artists")

    write_yaml({
        "top_tracks": tracks,
        "top_artists": artists,
    })

    print("\n✓ Spotify sync complete.")
    sys.exit(0)
