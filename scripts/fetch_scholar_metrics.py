#!/usr/bin/env python3
"""
Fetch citation metrics from Google Scholar and write to _data/scholar_metrics.yml.

Scrapes the public Google Scholar profile page to extract citation count,
h-index, i10-index, and paper count.

Falls back to Semantic Scholar API if Google Scholar scraping fails.

Usage:
    python scripts/fetch_scholar_metrics.py

Dependencies:
    pip install requests pyyaml beautifulsoup4
"""

import os
import re
import sys
import time
from pathlib import Path

DATA_DIR = Path("_data")
GOOGLE_SCHOLAR_ID = os.getenv("GOOGLE_SCHOLAR_ID", "D2X7Qv0AAAAJ")
S2_AUTHOR_ID = os.getenv("S2_AUTHOR_ID", "2238727014")
S2_API_KEY = os.getenv("S2_API_KEY", "").strip()


def fetch_google_scholar():
    """Scrape metrics from Google Scholar profile page."""
    import requests
    from bs4 import BeautifulSoup

    print(f"\n── Google Scholar metrics ({GOOGLE_SCHOLAR_ID}) ──")

    url = f"https://scholar.google.com/citations?user={GOOGLE_SCHOLAR_ID}&hl=en"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching Google Scholar: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Extract metrics from the table
    # The metrics table has rows: Citations, h-index, i10-index
    # Columns: All, Since YYYY
    metrics = {}

    table = soup.find("table", id="gsc_rsb_st")
    if not table:
        print("  ERROR: Could not find metrics table (may be rate-limited)")
        return None

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)  # "All" column
            try:
                value = int(value)
            except ValueError:
                continue

            if "citation" in label:
                metrics["total_citations"] = value
            elif "h-index" in label:
                metrics["h_index"] = value
            elif "i10" in label:
                metrics["i10_index"] = value

    # Extract name
    name_el = soup.find("div", id="gsc_prf_in")
    if name_el:
        metrics["name"] = name_el.get_text(strip=True)

    # Count papers (number of entries in the publication list)
    papers = soup.find_all("tr", class_="gsc_a_tr")
    metrics["paper_count"] = len(papers) if papers else 0

    # If we got at least citations, consider it a success
    if "total_citations" not in metrics:
        print("  ERROR: Could not parse citation metrics")
        return None

    # Extract top papers
    top_papers = []
    for paper in papers[:5]:
        title_el = paper.find("a", class_="gsc_a_at")
        cite_el = paper.find("a", class_="gsc_a_ac")
        year_el = paper.find("span", class_="gsc_a_h")

        if title_el:
            citations = 0
            if cite_el:
                try:
                    citations = int(cite_el.get_text(strip=True))
                except ValueError:
                    pass
            if citations > 0:
                year = None
                if year_el:
                    try:
                        year = int(year_el.get_text(strip=True))
                    except ValueError:
                        pass
                top_papers.append({
                    "title": title_el.get_text(strip=True),
                    "citations": citations,
                    "year": year,
                })

    metrics["top_papers"] = top_papers
    metrics["last_updated"] = time.strftime("%Y-%m-%d")
    metrics["source"] = "google_scholar"

    print(f"  Citations: {metrics['total_citations']}, h-index: {metrics['h_index']}, "
          f"i10-index: {metrics.get('i10_index', 'N/A')}, Papers: {metrics['paper_count']}")

    return metrics


def fetch_semantic_scholar():
    """Fallback: fetch from Semantic Scholar API."""
    import requests

    print(f"\n── Semantic Scholar fallback (author {S2_AUTHOR_ID}) ──")

    headers = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

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

    papers = data.get("papers", [])
    i10_index = sum(1 for p in papers if (p.get("citationCount") or 0) >= 10)

    top_papers = sorted(papers, key=lambda p: p.get("citationCount") or 0, reverse=True)[:5]
    top_papers_data = [
        {"title": p.get("title", ""), "citations": p.get("citationCount", 0), "year": p.get("year")}
        for p in top_papers if (p.get("citationCount") or 0) > 0
    ]

    metrics = {
        "name": data.get("name", ""),
        "total_citations": data.get("citationCount", 0),
        "h_index": data.get("hIndex", 0),
        "i10_index": i10_index,
        "paper_count": data.get("paperCount", 0),
        "top_papers": top_papers_data,
        "last_updated": time.strftime("%Y-%m-%d"),
        "source": "semantic_scholar",
    }

    print(f"  Citations: {metrics['total_citations']}, h-index: {metrics['h_index']}, Papers: {metrics['paper_count']}")
    return metrics


def write_yaml(metrics):
    import yaml

    DATA_DIR.mkdir(exist_ok=True)
    outpath = DATA_DIR / "scholar_metrics.yml"

    with open(outpath, "w", encoding="utf-8") as f:
        yaml.dump(metrics, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"  Wrote metrics to {outpath}")


if __name__ == "__main__":
    # Try Google Scholar first, fall back to Semantic Scholar
    metrics = fetch_google_scholar()
    if not metrics:
        print("  Falling back to Semantic Scholar...")
        metrics = fetch_semantic_scholar()

    if metrics:
        write_yaml(metrics)
    else:
        print("  Failed to fetch metrics from any source.")
    sys.exit(0)
