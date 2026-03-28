#!/usr/bin/env python3
"""
Fetch publications from Semantic Scholar API and generate Jekyll markdown files.

Why Semantic Scholar instead of Google Scholar?
  Google Scholar aggressively blocks GitHub Actions IPs.
  Semantic Scholar (https://api.semanticscholar.org) has a free, public REST API
  that works reliably from CI runners.

Auto-discovery:
  On first run the script finds your Semantic Scholar author ID by looking up
  a known arXiv paper you authored (KNOWN_ARXIV_ID below).  On subsequent runs
  it reuses the cached ID stored in scripts/.s2_author_id.

Dependencies: only the stdlib + requests  (pip install requests)
"""

import os
import re
import sys
import time
import json
import hashlib
import textwrap
from datetime import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
# A paper you definitely authored — used to bootstrap author ID discovery.
# ArXiv ID or DOI (without "arXiv:" prefix) is fine.
KNOWN_ARXIV_ID   = "2408.06034"          # "Ontology Landscape" paper

# Override: set S2_AUTHOR_ID env-var or fill in here to skip auto-discovery.
S2_AUTHOR_ID_ENV = os.getenv("S2_AUTHOR_ID", "").strip()

OUTPUT_DIR       = Path("_publications")
CACHE_FILE       = Path("scripts/.s2_author_id")   # persisted across runs
MAX_PUBS         = 100
REQUEST_SLEEP    = 1.2    # seconds between API calls (stay under rate limit)
# ─────────────────────────────────────────────────────────────────────────────

BASE = "https://api.semanticscholar.org/graph/v1"
HEADERS = {"User-Agent": "ebrahimnorouzi-website-bot/1.0"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(url: str, params: dict = None, retries: int = 3) -> dict:
    """GET with retries and polite rate limiting."""
    try:
        import requests as req_lib
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        sys.exit(0)

    for attempt in range(retries):
        try:
            r = req_lib.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s …")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(5)
    return {}


def slugify(text: str, maxlen: int = 55) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:maxlen].strip("-")


def existing_titles() -> set:
    """Return lowercased set of titles already in _publications/."""
    titles = set()
    for f in OUTPUT_DIR.glob("*.md"):
        m = re.search(r'^title:\s*"?([^"\n]+)"?', f.read_text(encoding="utf-8"), re.M)
        if m:
            titles.add(m.group(1).strip().lower())
    return titles


# ── Author ID discovery ───────────────────────────────────────────────────────

def load_cached_id() -> str:
    if CACHE_FILE.exists():
        cached = CACHE_FILE.read_text().strip()
        if cached:
            return cached
    return ""


def save_cached_id(author_id: str):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(author_id)


def find_author_id_via_paper(arxiv_id: str) -> str:
    """Look up a paper by arXiv ID and return the first matching author ID."""
    print(f"Looking up arXiv:{arxiv_id} to find author ID …")
    time.sleep(REQUEST_SLEEP)
    data = get(f"{BASE}/paper/arXiv:{arxiv_id}", params={"fields": "authors"})
    authors = data.get("authors", [])
    if not authors:
        print("  No authors found in paper lookup.")
        return ""
    # The first author whose name contains "Norouzi"
    for a in authors:
        if "norouzi" in a.get("name", "").lower():
            print(f"  Found: {a['name']}  ID={a['authorId']}")
            return a["authorId"]
    # Fallback: return first author
    first = authors[0]
    print(f"  Using first author: {first.get('name')}  ID={first.get('authorId')}")
    return first.get("authorId", "")


def get_author_id() -> str:
    if S2_AUTHOR_ID_ENV:
        return S2_AUTHOR_ID_ENV

    cached = load_cached_id()
    if cached:
        print(f"Using cached Semantic Scholar author ID: {cached}")
        return cached

    author_id = find_author_id_via_paper(KNOWN_ARXIV_ID)
    if author_id:
        save_cached_id(author_id)
    return author_id


# ── Paper fetching ────────────────────────────────────────────────────────────

PAPER_FIELDS = ",".join([
    "title", "year", "venue", "abstract", "authors",
    "externalIds", "openAccessPdf", "publicationDate",
    "publicationTypes", "citationCount",
])


def fetch_all_papers(author_id: str) -> list:
    papers, offset = [], 0
    while True:
        time.sleep(REQUEST_SLEEP)
        data = get(
            f"{BASE}/author/{author_id}/papers",
            params={"fields": PAPER_FIELDS, "limit": 100, "offset": offset},
        )
        batch = data.get("data", [])
        papers.extend(batch)
        if len(batch) < 100 or len(papers) >= MAX_PUBS:
            break
        offset += 100
    return papers[:MAX_PUBS]


# ── Markdown generation ───────────────────────────────────────────────────────

def paper_url(paper: dict) -> str:
    eids = paper.get("externalIds") or {}
    if arxiv := eids.get("ArXiv"):
        return f"https://arxiv.org/abs/{arxiv}"
    if doi := eids.get("DOI"):
        return f"https://doi.org/{doi}"
    if pdf := paper.get("openAccessPdf"):
        return pdf.get("url", "")
    return ""


def paper_date(paper: dict) -> str:
    if pub_date := paper.get("publicationDate"):
        return pub_date[:10]          # "YYYY-MM-DD"
    year = paper.get("year") or 1900
    return f"{year}-01-01"


def make_markdown(paper: dict) -> str:
    title    = (paper.get("title") or "").replace('"', '\\"').strip()
    abstract = (paper.get("abstract") or "").strip()
    venue    = (paper.get("venue") or "").replace("'", "&#39;").strip()
    authors  = ", ".join(a.get("name", "") for a in (paper.get("authors") or []))
    year     = paper.get("year") or ""
    url      = paper_url(paper)
    date_str = paper_date(paper)
    excerpt  = textwrap.shorten(abstract, width=280, placeholder="…").replace("'", "&#39;")
    citation = f'{authors} ({year}). "{title}". {venue}.'.replace("'", "&#39;")
    cites    = paper.get("citationCount", 0) or 0

    return f'''---
title: "{title}"
collection: publications
permalink: /publication/{slugify(title)}/
excerpt: '{excerpt}'
date: {date_str}
venue: '{venue}'
paperurl: '{url}'
citation: '{citation}'
citation_count: {cites}
---
{abstract}

[View on Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/{paper.get("paperId","")}){{:target="_blank"}}
{f'[Download / Open Access]({url}){{:target="_blank"}}' if url else ''}

Recommended citation: {authors} ({year}). "{(paper.get("title") or "").strip()}". {venue}.
'''


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    author_id = get_author_id()
    if not author_id:
        print("ERROR: could not determine Semantic Scholar author ID.")
        print("  → Set S2_AUTHOR_ID env var or update KNOWN_ARXIV_ID in the script.")
        sys.exit(0)   # exit 0 so workflow doesn't fail

    print(f"\nFetching papers for S2 author: {author_id}")
    papers = fetch_all_papers(author_id)
    print(f"Found {len(papers)} papers on Semantic Scholar.")

    known = existing_titles()
    new_count = skip_count = 0

    for paper in papers:
        title = (paper.get("title") or "").strip()
        if not title:
            continue

        if title.lower() in known:
            skip_count += 1
            print(f"  [skip]  {title[:72]}")
            continue

        date_str = paper_date(paper)
        filename = f"{date_str}-{slugify(title)}.md"
        filepath = OUTPUT_DIR / filename

        # Don't overwrite a file that already exists with a different slug
        if filepath.exists():
            skip_count += 1
            continue

        filepath.write_text(make_markdown(paper), encoding="utf-8")
        new_count += 1
        print(f"  [new]   {title[:72]}")

    print(f"\nDone — {new_count} new, {skip_count} skipped.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nERROR: {e}")
        # Exit 0 so the GitHub Actions workflow is not marked as failed;
        # the commit step will simply find no changes and skip.
        sys.exit(0)
