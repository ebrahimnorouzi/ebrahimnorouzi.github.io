#!/usr/bin/env python3
"""
Fetch recent Strava activities and write them to _data/strava_activities.yml.

Requires STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN
as environment variables (stored as GitHub Secrets).

Usage:
    python scripts/fetch_strava_activities.py

Dependencies:
    pip install requests pyyaml
"""

import os
import sys
from pathlib import Path

DATA_DIR = Path("_data")
MAX_ACTIVITIES = int(os.getenv("MAX_ACTIVITIES", "50"))


def get_access_token():
    import requests

    client_id = os.getenv("STRAVA_CLIENT_ID", "")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET", "")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN", "")

    if not all([client_id, client_secret, refresh_token]):
        print("  ERROR: Missing STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, or STRAVA_REFRESH_TOKEN")
        return None

    try:
        r = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    except Exception as e:
        print(f"  ERROR: Could not refresh Strava token — {e}")
        return None


def fetch_activities():
    import requests

    print("\n── Strava Activities ──")

    token = get_access_token()
    if not token:
        return []

    activities = []
    page = 1
    while len(activities) < MAX_ACTIVITIES:
        try:
            r = requests.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers={"Authorization": f"Bearer {token}"},
                params={"per_page": 50, "page": page},
                timeout=20,
            )
            r.raise_for_status()
            batch = r.json()
        except Exception as e:
            print(f"  ERROR: {e}")
            break

        if not batch:
            break

        for a in batch:
            activities.append({
                "name": a.get("name", ""),
                "type": a.get("sport_type", a.get("type", "")),
                "date": a.get("start_date_local", ""),
                "distance_km": round(a.get("distance", 0) / 1000, 2),
                "moving_time_min": round(a.get("moving_time", 0) / 60, 1),
                "elapsed_time_min": round(a.get("elapsed_time", 0) / 60, 1),
                "elevation_gain_m": round(a.get("total_elevation_gain", 0), 1),
                "average_speed_kmh": round(a.get("average_speed", 0) * 3.6, 1),
                "max_speed_kmh": round(a.get("max_speed", 0) * 3.6, 1),
                "average_heartrate": a.get("average_heartrate"),
                "max_heartrate": a.get("max_heartrate"),
                "kudos": a.get("kudos_count", 0),
                "polyline": (a.get("map") or {}).get("summary_polyline", ""),
                "strava_url": f"https://www.strava.com/activities/{a['id']}",
            })

        page += 1
        if len(batch) < 50:
            break

    return activities[:MAX_ACTIVITIES]


def compute_stats(activities):
    """Compute summary statistics."""
    from collections import defaultdict

    stats = {
        "total_activities": len(activities),
        "total_distance_km": 0,
        "total_time_hours": 0,
        "total_elevation_m": 0,
        "by_type": {},
    }

    type_data = defaultdict(lambda: {"count": 0, "distance_km": 0, "time_hours": 0})

    for a in activities:
        stats["total_distance_km"] += a["distance_km"]
        stats["total_time_hours"] += a["moving_time_min"] / 60
        stats["total_elevation_m"] += a["elevation_gain_m"]

        t = a["type"]
        type_data[t]["count"] += 1
        type_data[t]["distance_km"] += a["distance_km"]
        type_data[t]["time_hours"] += a["moving_time_min"] / 60

    stats["total_distance_km"] = round(stats["total_distance_km"], 1)
    stats["total_time_hours"] = round(stats["total_time_hours"], 1)
    stats["total_elevation_m"] = round(stats["total_elevation_m"], 1)

    for t, d in type_data.items():
        stats["by_type"][t] = {
            "count": d["count"],
            "distance_km": round(d["distance_km"], 1),
            "time_hours": round(d["time_hours"], 1),
        }

    return stats


def write_yaml(activities, stats):
    import yaml

    DATA_DIR.mkdir(exist_ok=True)

    data = {"stats": stats, "activities": activities}
    outpath = DATA_DIR / "strava_activities.yml"

    with open(outpath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  Wrote {len(activities)} activities to {outpath}")


if __name__ == "__main__":
    activities = fetch_activities()
    if activities:
        stats = compute_stats(activities)
        write_yaml(activities, stats)
    else:
        print("  No activities fetched (check Strava secrets).")
    print(f"\n✓ Total activities: {len(activities)}")
    sys.exit(0)
