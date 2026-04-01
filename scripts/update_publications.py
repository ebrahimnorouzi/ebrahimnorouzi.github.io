#!/usr/bin/env python3
"""
Fetch publications from Semantic Scholar + arXiv + Zenodo and generate Jekyll markdown files.

Sources:
  1. Semantic Scholar API  — rich metadata, citation counts, venue info
  2. arXiv API             — fallback / supplement; no auth required
  3. Zenodo API            — posters, presentations, datasets, preprints

Configuration (env vars / GitHub Secrets):
  S2_API_KEY       — Semantic Scholar API key (higher rate limits; recommended)
  S2_AUTHOR_ID     — Semantic Scholar author ID (skips auto-discovery)
  ARXIV_AUTHOR     — Author name for arXiv search (e.g. "Ebrahim Norouzi")
  ZENODO_AUTHOR    — Author name as stored in Zenodo (e.g. "Norouzi, Ebrahim")
  ZENODO_API_TOKEN — Zenodo personal access token (optional; raises rate limits)

Dependencies: pip install requests
"""

import os
import re
import sys
import time
import textwrap
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
KNOWN_ARXIV_ID   = "2408.06034"          # bootstrap paper for S2 author ID discovery
S2_AUTHOR_ID_ENV = os.getenv("S2_AUTHOR_ID", "2238727014").strip()
S2_API_KEY       = os.getenv("S2_API_KEY", "").strip()
ARXIV_AUTHOR     = os.getenv("ARXIV_AUTHOR", "Ebrahim Norouzi")
ZENODO_AUTHOR    = os.getenv("ZENODO_AUTHOR", "Norouzi, Ebrahim")
ZENODO_API_TOKEN = os.getenv("ZENODO_API_TOKEN", "").strip()

OUTPUT_DIR       = Path("_publications")
CACHE_FILE       = Path("scripts/.s2_author_id")
MAX_PUBS         = 100
REQUEST_SLEEP    = 1.0   # polite delay between calls (reduced with API key)
# ─────────────────────────────────────────────────────────────────────────────

S2_BASE = "https://api.semanticscholar.org/graph/v1"


def s2_headers() -> dict:
    h = {"User-Agent": "ebrahimnorouzi-website-bot/1.0"}
    if S2_API_KEY:
        h["x-api-key"] = S2_API_KEY
    return h


# ── HTTP helper ───────────────────────────────────────────────────────────────

def get(url: str, params: dict = None, headers: dict = None, retries: int = 4) -> dict:
    try:
        import requests as req_lib
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        sys.exit(1)

    h = headers or {}
    for attempt in range(retries):
        try:
            r = req_lib.get(url, params=params, headers=h, timeout=30)
            if r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s … (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return {}


def get_text(url: str, params: dict = None, retries: int = 4) -> str:
    """GET returning raw text (for arXiv Atom feed)."""
    try:
        import requests as req_lib
    except ImportError:
        sys.exit(1)

    for attempt in range(retries):
        try:
            r = req_lib.get(url, params=params,
                            headers={"User-Agent": "ebrahimnorouzi-website-bot/1.0"},
                            timeout=30)
            if r.status_code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.text
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    return ""


# ── Shared utilities ──────────────────────────────────────────────────────────

def slugify(text: str, maxlen: int = 55) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:maxlen].strip("-")


def existing_titles() -> set:
    titles = set()
    for f in OUTPUT_DIR.glob("*.md"):
        m = re.search(r'^title:\s*"?([^"\n]+)"?', f.read_text(encoding="utf-8"), re.M)
        if m:
            titles.add(m.group(1).strip().lower())
    return titles


def write_pub(filename: str, content: str) -> bool:
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        return False
    filepath.write_text(content, encoding="utf-8")
    print(f"  [new]   {filename}")
    return True


# ── Semantic Scholar ──────────────────────────────────────────────────────────

def load_cached_s2_id() -> str:
    if CACHE_FILE.exists():
        v = CACHE_FILE.read_text().strip()
        if v:
            return v
    return ""


def save_cached_s2_id(author_id: str):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(author_id)


def find_s2_author_id() -> str:
    print(f"Looking up arXiv:{KNOWN_ARXIV_ID} to discover S2 author ID …")
    time.sleep(REQUEST_SLEEP)
    data = get(f"{S2_BASE}/paper/arXiv:{KNOWN_ARXIV_ID}",
               params={"fields": "authors"}, headers=s2_headers())
    for a in data.get("authors", []):
        if "norouzi" in a.get("name", "").lower():
            print(f"  Found: {a['name']}  ID={a['authorId']}")
            return a["authorId"]
    authors = data.get("authors", [])
    if authors:
        first = authors[0]
        print(f"  Using first author: {first.get('name')}  ID={first.get('authorId')}")
        return first.get("authorId", "")
    return ""


def get_s2_author_id() -> str:
    if S2_AUTHOR_ID_ENV:
        return S2_AUTHOR_ID_ENV
    cached = load_cached_s2_id()
    if cached:
        print(f"Using cached S2 author ID: {cached}")
        return cached
    author_id = find_s2_author_id()
    if author_id:
        save_cached_s2_id(author_id)
    return author_id


PAPER_FIELDS = ",".join([
    "title", "year", "venue", "abstract", "authors",
    "externalIds", "openAccessPdf", "publicationDate",
    "publicationTypes", "citationCount",
])


def fetch_s2_papers(author_id: str) -> list:
    papers, offset = [], 0
    while True:
        time.sleep(REQUEST_SLEEP)
        data = get(
            f"{S2_BASE}/author/{author_id}/papers",
            params={"fields": PAPER_FIELDS, "limit": 100, "offset": offset},
            headers=s2_headers(),
        )
        batch = data.get("data", [])
        papers.extend(batch)
        if len(batch) < 100 or len(papers) >= MAX_PUBS:
            break
        offset += 100
    return papers[:MAX_PUBS]


def s2_paper_url(paper: dict) -> str:
    eids = paper.get("externalIds") or {}
    if arxiv := eids.get("ArXiv"):
        return f"https://arxiv.org/abs/{arxiv}"
    if doi := eids.get("DOI"):
        return f"https://doi.org/{doi}"
    if pdf := paper.get("openAccessPdf"):
        return pdf.get("url", "")
    return ""


def s2_paper_date(paper: dict) -> str:
    if pub_date := paper.get("publicationDate"):
        return pub_date[:10]
    year = paper.get("year") or 1900
    return f"{year}-01-01"


def s2_make_markdown(paper: dict) -> str:
    title    = (paper.get("title") or "").replace('"', '\\"').strip()
    abstract = (paper.get("abstract") or "").strip()
    venue    = (paper.get("venue") or "").replace("'", "&#39;").strip()
    authors  = ", ".join(a.get("name", "") for a in (paper.get("authors") or []))
    year     = paper.get("year") or ""
    url      = s2_paper_url(paper)
    date_str = s2_paper_date(paper)
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
source: semantic_scholar
---
{abstract}

[View on Semantic Scholar](https://www.semanticscholar.org/paper/{paper.get("paperId","")}){{:target="_blank"}}
{f'[Download / Open Access]({url}){{:target="_blank"}}' if url else ''}

Recommended citation: {authors} ({year}). "{(paper.get("title") or "").strip()}". {venue}.
'''


def run_semantic_scholar(known: set) -> int:
    print("\n── Semantic Scholar ──")
    if S2_API_KEY:
        print("  API key detected — using authenticated requests.")
    else:
        print("  WARNING: No S2_API_KEY set. Unauthenticated requests may be rate-limited.")

    author_id = get_s2_author_id()
    if not author_id:
        print("  ERROR: could not determine S2 author ID.")
        print("  → Set S2_AUTHOR_ID secret or verify KNOWN_ARXIV_ID in script.")
        return -1   # signal failure

    print(f"  Fetching papers for author ID: {author_id}")
    papers = fetch_s2_papers(author_id)
    print(f"  Found {len(papers)} papers.")

    new_count = 0
    for paper in papers:
        title = (paper.get("title") or "").strip()
        if not title or title.lower() in known:
            continue
        date_str = s2_paper_date(paper)
        filename = f"{date_str}-{slugify(title)}.md"
        if write_pub(filename, s2_make_markdown(paper)):
            known.add(title.lower())
            new_count += 1

    print(f"  Done — {new_count} new from Semantic Scholar.")
    return new_count


# ── arXiv ─────────────────────────────────────────────────────────────────────

ARXIV_NS = "http://www.w3.org/2005/Atom"


def fetch_arxiv_papers(author: str, max_results: int = 100) -> list:
    """Query arXiv API for papers by author name."""
    # arXiv search uses Lucene syntax; quote the name for exact match
    query = f'au:"{author}"'
    time.sleep(REQUEST_SLEEP)
    xml_text = get_text(
        "https://export.arxiv.org/api/query",
        params={"search_query": query, "start": 0, "max_results": max_results,
                "sortBy": "submittedDate", "sortOrder": "descending"},
    )
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  ERROR parsing arXiv response: {e}")
        return []
    return root.findall(f"{{{ARXIV_NS}}}entry")


def arxiv_make_markdown(entry) -> tuple[str, str, str]:
    """Return (title, date_str, markdown) for an arXiv entry element."""
    ns = ARXIV_NS

    def txt(tag):
        el = entry.find(f"{{{ns}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    title    = re.sub(r"\s+", " ", txt("title"))
    abstract = re.sub(r"\s+", " ", txt("summary"))
    published = txt("published")          # e.g. "2024-08-12T00:00:00Z"
    arxiv_id_raw = txt("id")             # full URL like https://arxiv.org/abs/2408.06034v1
    arxiv_id = re.search(r"abs/(\d{4}\.\d+)", arxiv_id_raw)
    arxiv_id = arxiv_id.group(1) if arxiv_id else ""
    url      = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else arxiv_id_raw

    authors = [
        (a.find(f"{{{ns}}}name").text or "").strip()
        for a in entry.findall(f"{{{ns}}}author")
        if a.find(f"{{{ns}}}name") is not None
    ]
    authors_str = ", ".join(authors)

    try:
        date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        date_str = date.strftime("%Y-%m-%d")
        year = date.year
    except Exception:
        date_str = "1900-01-01"
        year = ""

    categories = [c.get("term", "") for c in entry.findall(f"{{{ns}}}category")]
    venue = "arXiv:" + (categories[0] if categories else "cs")

    title_esc  = title.replace('"', '\\"')
    excerpt    = textwrap.shorten(abstract, width=280, placeholder="…").replace("'", "&#39;")
    venue_esc  = venue.replace("'", "&#39;")
    citation   = f'{authors_str} ({year}). "{title}". {venue}.'.replace("'", "&#39;")

    md = f'''---
title: "{title_esc}"
collection: publications
permalink: /publication/{slugify(title)}/
excerpt: '{excerpt}'
date: {date_str}
venue: '{venue_esc}'
paperurl: '{url}'
citation: '{citation}'
citation_count: 0
source: arxiv
---
{abstract}

[View on arXiv]({url}){{:target="_blank"}}

Recommended citation: {authors_str} ({year}). "{title}". {venue}.
'''
    return title, date_str, md


def run_arxiv(known: set) -> int:
    print(f"\n── arXiv (author: {ARXIV_AUTHOR}) ──")
    entries = fetch_arxiv_papers(ARXIV_AUTHOR)
    if not entries:
        print("  No entries returned from arXiv.")
        return 0

    print(f"  Found {len(entries)} entries.")
    new_count = 0
    for entry in entries:
        title, date_str, md = arxiv_make_markdown(entry)
        if not title or title.lower() in known:
            continue
        filename = f"{date_str}-{slugify(title)}.md"
        if write_pub(filename, md):
            known.add(title.lower())
            new_count += 1

    print(f"  Done — {new_count} new from arXiv.")
    return new_count


# ── Zenodo ───────────────────────────────────────────────────────────────────

def zenodo_headers() -> dict:
    h = {"User-Agent": "ebrahimnorouzi-website-bot/1.0"}
    if ZENODO_API_TOKEN:
        h["Authorization"] = f"Bearer {ZENODO_API_TOKEN}"
    return h


def fetch_zenodo_records(author: str) -> list:
    """Fetch all Zenodo records where the author name appears as a creator."""
    records, page = [], 1
    while True:
        time.sleep(REQUEST_SLEEP)
        params = {"q": f'"{author}"', "size": 25, "page": page, "sort": "mostrecent"}
        data = get("https://zenodo.org/api/records", params=params,
                   headers=zenodo_headers())
        hits = data.get("hits", {}).get("hits", [])
        author_lower = author.lower()
        matching = [
            h for h in hits
            if any(author_lower in c.get("name", "").lower()
                   for c in h.get("metadata", {}).get("creators", []))
        ]
        records.extend(matching)
        if len(hits) < 25:
            break
        page += 1
    return records


def zenodo_make_markdown(record: dict) -> str:
    meta     = record.get("metadata", {})
    title    = (meta.get("title") or "").replace('"', '\\"').strip()
    desc     = re.sub(r"<[^>]+>", "", meta.get("description") or "").strip()
    desc     = re.sub(r"\s+", " ", desc)
    creators = meta.get("creators", [])
    authors  = ", ".join(c.get("name", "") for c in creators)
    doi      = meta.get("doi", "")
    url      = f"https://doi.org/{doi}" if doi else f"https://zenodo.org/record/{record['id']}"
    date_str = (meta.get("publication_date") or "1900-01-01")[:10]
    year     = date_str[:4]
    rtype    = meta.get("resource_type", {})
    # rtype["title"] is already the human-readable label ("Presentation",
    # "Conference paper", "Dataset", etc.) — use it directly to avoid
    # duplicates like "Zenodo (Presentation: Presentation)".
    venue    = f"Zenodo ({rtype.get('title', 'Record')})"

    excerpt   = textwrap.shorten(desc or title, width=280, placeholder="…").replace("'", "&#39;")
    venue_esc = venue.replace("'", "&#39;")
    doi_url   = f"https://doi.org/{doi}" if doi else url
    citation  = f'{authors} ({year}). "{title}". {venue}. {doi_url}'.replace("'", "&#39;")

    files   = record.get("files", [])
    pdf_url = next((f["links"]["self"] for f in files if f.get("type") == "pdf"), "")

    return f'''---
title: "{title}"
collection: publications
permalink: /publication/{slugify(title)}/
excerpt: '{excerpt}'
date: {date_str}
venue: '{venue_esc}'
paperurl: '{url}'
citation: '{citation}'
citation_count: 0
source: zenodo
zenodo_id: {record["id"]}
---
{desc or title}

[View on Zenodo]({url}){{:target="_blank"}}
{f'[Download PDF]({pdf_url}){{:target="_blank"}}' if pdf_url else ''}

Recommended citation: {authors} ({year}). "{title}". {venue}. <{url}>
'''


def run_zenodo(known: set) -> int:
    print(f"\n── Zenodo (author: {ZENODO_AUTHOR}) ──")
    if ZENODO_API_TOKEN:
        print("  API token detected — using authenticated requests.")

    records = fetch_zenodo_records(ZENODO_AUTHOR)
    print(f"  Found {len(records)} records.")

    new_count = 0
    for record in records:
        meta  = record.get("metadata", {})
        title = (meta.get("title") or "").strip()
        if not title or title.lower() in known:
            continue
        date_str = (meta.get("publication_date") or "1900-01-01")[:10]
        filename = f"{date_str}-zenodo-{slugify(title)}.md"
        if write_pub(filename, zenodo_make_markdown(record)):
            known.add(title.lower())
            new_count += 1

    print(f"  Done — {new_count} new from Zenodo.")
    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    known = existing_titles()

    s2_result     = run_semantic_scholar(known)
    arxiv_result  = run_arxiv(known)
    zenodo_result = run_zenodo(known)

    s2_new     = max(s2_result, 0)
    arxiv_new  = max(arxiv_result, 0)
    zenodo_new = max(zenodo_result, 0)
    total      = s2_new + arxiv_new + zenodo_new

    print(f"\n✓ Total new publications: {total}  (S2: {s2_new}, arXiv: {arxiv_new}, Zenodo: {zenodo_new})")

    # Fail if ALL sources errored — at least one must succeed.
    if s2_result == -1 and arxiv_result == 0 and zenodo_result == 0:
        print("\nERROR: All sources failed. Check S2_API_KEY / S2_AUTHOR_ID secrets.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nFATAL: {e}")
        sys.exit(1)
