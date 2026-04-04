#!/usr/bin/env python3
"""
Fetch citation metrics from Semantic Scholar and write to _data/scholar_metrics.yml.

Uses the Semantic Scholar API (public, no auth needed for basic queries).

Usage:
    python scripts/fetch_scholar_metrics.py

Dependencies:
    pip install requests pyyaml
"""

import os
import sys
import time
from pathlib import Path

DATA_DIR = Path("_data")
S2_AUTHOR_ID = os.getenv("S2_AUTHOR_ID", "2238727014")
S2_API_KEY = os.getenv("S2_API_KEY", "").strip()


def fetch_metrics():
    import requests

    print(f"\n── Semantic Scholar metrics (author {S2_AUTHOR_ID}) ──")

    headers = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    # Fetch author details
    try:
        r = requests.get(
            f"https://api.semanticscholar.org/graph/v1/author/{S2_AUTHOR_ID}",
            params={"fields": "name,hIndex,citationCount,paperCount,papers.citationCount,papers.year,papers.title"},
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    # Compute metrics
    papers = data.get("papers", [])
    total_citations = data.get("citationCount", 0)
    h_index = data.get("hIndex", 0)
    paper_count = data.get("paperCount", 0)

    # i10-index: papers with >= 10 citations
    i10_index = sum(1 for p in papers if (p.get("citationCount") or 0) >= 10)

    # Most cited papers
    top_papers = sorted(papers, key=lambda p: p.get("citationCount") or 0, reverse=True)[:5]
    top_papers_data = []
    for p in top_papers:
        if (p.get("citationCount") or 0) > 0:
            top_papers_data.append({
                "title": p.get("title", ""),
                "citations": p.get("citationCount", 0),
                "year": p.get("year"),
            })

    # Citations by year (rough estimate from papers)
    year_citations = {}
    for p in papers:
        yr = p.get("year")
        if yr:
            year_citations[yr] = year_citations.get(yr, 0) + (p.get("citationCount") or 0)

    metrics = {
        "name": data.get("name", ""),
        "total_citations": total_citations,
        "h_index": h_index,
        "i10_index": i10_index,
        "paper_count": paper_count,
        "top_papers": top_papers_data,
        "last_updated": time.strftime("%Y-%m-%d"),
    }

    return metrics


def write_yaml(metrics):
    import yaml

    DATA_DIR.mkdir(exist_ok=True)
    outpath = DATA_DIR / "scholar_metrics.yml"

    with open(outpath, "w", encoding="utf-8") as f:
        yaml.dump(metrics, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  Wrote metrics to {outpath}")
    print(f"  Citations: {metrics['total_citations']}, h-index: {metrics['h_index']}, Papers: {metrics['paper_count']}")


if __name__ == "__main__":
    metrics = fetch_metrics()
    if metrics:
        write_yaml(metrics)
    else:
        print("  Failed to fetch metrics.")
    sys.exit(0)
