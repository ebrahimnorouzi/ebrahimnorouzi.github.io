#!/usr/bin/env python3
"""
Fetch publications from Google Scholar and generate Jekyll markdown files.

Usage:
    python scripts/update_publications.py

Requirements:
    pip install scholarly

The script uses the `scholarly` library to scrape Google Scholar.
It creates/updates files in _publications/ using the naming convention:
    YYYY-MM-DD-<slug>.md

Set SCHOLAR_ID to your Google Scholar user ID (the string after ?user= in your profile URL).
"""

import os
import re
import time
import hashlib
from datetime import datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────
SCHOLAR_ID     = "D2X7Qv0AAAAJ"          # Ebrahim Norouzi
OUTPUT_DIR     = Path("_publications")
MAX_PUBS       = 100                       # safety cap
SLEEP_BETWEEN  = 3                         # seconds between Scholar requests
# ─────────────────────────────────────────────────────────────────────────────


def slugify(text: str) -> str:
    """Convert a string to a URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-")


def clean(value) -> str:
    """Strip None / list artefacts from scholarly data."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value).strip()


def existing_slugs() -> dict:
    """Return a mapping {title_hash: filepath} for already-created files."""
    mapping = {}
    for f in OUTPUT_DIR.glob("*.md"):
        # read just the front-matter title
        content = f.read_text(encoding="utf-8")
        m = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        if m:
            key = hashlib.md5(m.group(1).strip().lower().encode()).hexdigest()
            mapping[key] = f
    return mapping


def make_markdown(pub_info: dict) -> str:
    """Render a Jekyll front-matter + body markdown string."""
    title    = clean(pub_info.get("title"))
    authors  = clean(pub_info.get("authors"))
    venue    = clean(pub_info.get("venue"))
    year     = clean(pub_info.get("year"))
    abstract = clean(pub_info.get("abstract"))
    url      = clean(pub_info.get("url"))
    citation = clean(pub_info.get("citation"))

    # Build date string (default to Jan 1 of the year)
    date_str = f"{year}-01-01" if year else "1900-01-01"

    # Escape YAML special characters in title
    title_yaml = title.replace('"', '\\"')

    body = f'''---
title: "{title_yaml}"
collection: publications
permalink: /publication/{slugify(title)}/
excerpt: '{abstract[:300].replace("'", "&#39;")}{"..." if len(abstract) > 300 else ""}'
date: {date_str}
venue: '{venue.replace("'", "&#39;")}'
paperurl: '{url}'
citation: '{citation.replace("'", "&#39;")}'
---
{abstract}

[View on Google Scholar]({url}){{:target="_blank"}}

Recommended citation: {citation}
'''
    return body


def fetch_publications():
    """Main routine: fetch from Scholar, write markdown files."""
    try:
        from scholarly import scholarly as sc
    except ImportError:
        print("ERROR: `scholarly` not installed. Run: pip install scholarly")
        raise SystemExit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    existing = existing_slugs()
    new_count = 0
    skip_count = 0

    print(f"Fetching author profile: {SCHOLAR_ID}")
    try:
        author = sc.search_author_id(SCHOLAR_ID)
        sc.fill(author, sections=["publications"])
    except Exception as e:
        print(f"ERROR fetching author: {e}")
        raise SystemExit(1)

    pubs = author.get("publications", [])[:MAX_PUBS]
    print(f"Found {len(pubs)} publications")

    for i, pub in enumerate(pubs):
        try:
            time.sleep(SLEEP_BETWEEN)
            sc.fill(pub)

            bib      = pub.get("bib", {})
            title    = clean(bib.get("title"))
            if not title:
                continue

            title_key = hashlib.md5(title.lower().encode()).hexdigest()
            if title_key in existing:
                skip_count += 1
                print(f"  [skip]  {title[:70]}")
                continue

            year    = clean(bib.get("pub_year") or bib.get("year"))
            authors = clean(bib.get("author"))
            venue   = clean(bib.get("venue") or bib.get("journal") or bib.get("conference") or "")
            abstract = clean(bib.get("abstract") or "")
            url     = clean(pub.get("pub_url") or pub.get("eprint_url") or "")
            citation = f'{authors} ({year}). "{title}". {venue}.'

            pub_info = {
                "title":    title,
                "authors":  authors,
                "venue":    venue,
                "year":     year,
                "abstract": abstract,
                "url":      url,
                "citation": citation,
            }

            date_str = f"{year}-01-01" if year else "1900-01-01"
            filename = f"{date_str}-{slugify(title)}.md"
            filepath = OUTPUT_DIR / filename

            filepath.write_text(make_markdown(pub_info), encoding="utf-8")
            new_count += 1
            print(f"  [new]   {title[:70]}")

        except Exception as e:
            print(f"  [error] {e}")
            continue

    print(f"\nDone — {new_count} new, {skip_count} skipped.")


if __name__ == "__main__":
    fetch_publications()
