#!/usr/bin/env python3
"""
Fetch public GitHub repositories and write them to _data/github_repos.yml.

Usage:
    python scripts/fetch_github_repos.py

Dependencies:
    pip install requests pyyaml
"""

import os
import sys
from pathlib import Path

DATA_DIR = Path("_data")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "ebrahimnorouzi")
MAX_REPOS = int(os.getenv("MAX_REPOS", "30"))
EXCLUDE_FORKS = os.getenv("EXCLUDE_FORKS", "false").lower() == "true"


def fetch_repos():
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        return []

    print(f"\n── GitHub repos for {GITHUB_USERNAME} ──")

    headers = {}
    token = os.getenv("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"token {token}"

    repos = []
    page = 1
    while len(repos) < MAX_REPOS:
        try:
            r = requests.get(
                f"https://api.github.com/users/{GITHUB_USERNAME}/repos",
                params={
                    "per_page": min(MAX_REPOS - len(repos), 100),
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                    "type": "owner",
                },
                headers=headers,
                timeout=20,
            )
            r.raise_for_status()
            batch = r.json()
        except Exception as e:
            print(f"  ERROR: {e}")
            break

        if not batch:
            break

        for repo in batch:
            if EXCLUDE_FORKS and repo.get("fork"):
                continue
            repos.append({
                "name": repo["name"],
                "description": repo.get("description") or "",
                "url": repo["html_url"],
                "language": repo.get("language") or "",
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "fork": repo.get("fork", False),
                "topics": repo.get("topics", []),
                "updated_at": repo.get("updated_at", ""),
                "created_at": repo.get("created_at", ""),
                "homepage": repo.get("homepage") or "",
            })

        page += 1
        if len(batch) < 100:
            break

    # Sort: stars desc, then updated desc
    repos.sort(key=lambda r: (-r["stars"], r["updated_at"]), reverse=False)

    return repos


def write_yaml(repos):
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed. Run: pip install pyyaml")
        return

    DATA_DIR.mkdir(exist_ok=True)
    outpath = DATA_DIR / "github_repos.yml"

    with open(outpath, "w", encoding="utf-8") as f:
        yaml.dump(repos, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  Wrote {len(repos)} repos to {outpath}")


if __name__ == "__main__":
    repos = fetch_repos()
    if repos:
        write_yaml(repos)
    print(f"\n✓ Total repos fetched: {len(repos)}")
    sys.exit(0)
