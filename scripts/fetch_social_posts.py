#!/usr/bin/env python3
"""
Fetch posts from Mastodon and LinkedIn (via RSS) and create Jekyll _posts files.

Usage:
    python scripts/fetch_social_posts.py

Dependencies:
    pip install requests beautifulsoup4 feedparser

Configuration (edit the CONFIG block below or pass as env vars):
    MASTODON_INSTANCE  — e.g. sigmoid.social
    MASTODON_USERNAME  — e.g. enorouzi
    LINKEDIN_RSS_URL   — RSS URL from rss.app (see README below)
    MAX_POSTS_PER_SOURCE — max posts to import per run

──────────────────────────────────────────────────────────────
How to get LinkedIn RSS:
  1. Go to  https://rss.app  (free tier available)
  2. Create a feed from your LinkedIn profile URL
  3. Copy the generated RSS URL and set LINKEDIN_RSS_URL below
  Alternatively, Zapier / n8n can also export LinkedIn posts as RSS.
──────────────────────────────────────────────────────────────
"""

import os
import re
import sys
import html
import hashlib
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
MASTODON_INSTANCE      = os.getenv("MASTODON_INSTANCE",  "sigmoid.social")
MASTODON_USERNAME      = os.getenv("MASTODON_USERNAME",  "enorouzi")
LINKEDIN_RSS_URL       = os.getenv("LINKEDIN_RSS_URL",   "")   # set via GitHub Secret
MAX_POSTS_PER_SOURCE   = int(os.getenv("MAX_POSTS",       "20"))
POSTS_DIR              = Path("_posts")
MIN_CONTENT_LENGTH     = 30   # skip very short toots (boosts, reacts)
# ─────────────────────────────────────────────────────────────────────────────


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text: str, maxlen: int = 50) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:maxlen].strip("-")


def strip_html(raw: str) -> str:
    """Very lightweight HTML → plain text."""
    # Replace block-level tags with newlines
    raw = re.sub(r"<br\s*/?>",        "\n",  raw, flags=re.I)
    raw = re.sub(r"</p>",             "\n\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>",          "",     raw)
    raw = html.unescape(raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def frontmatter(**kv) -> str:
    lines = ["---"]
    for k, v in kv.items():
        v_str = str(v).replace("'", "&#39;")
        lines.append(f'{k}: "{v_str}"')
    lines.append("---\n")
    return "\n".join(lines)


def existing_post_ids(source: str) -> set:
    """Return set of already-imported source IDs to avoid duplicates."""
    ids = set()
    for f in POSTS_DIR.glob(f"*-{source}-*.md"):
        m = re.search(rf"{source}-([a-f0-9]+)\.md$", f.name)
        if m:
            ids.add(m.group(1))
    return ids


def write_post(date: datetime, source: str, uid: str, title: str, content: str,
               url: str = "", tags: list = None) -> bool:
    POSTS_DIR.mkdir(exist_ok=True)
    short_id = hashlib.md5(uid.encode()).hexdigest()[:10]
    date_str  = date.strftime("%Y-%m-%d")
    slug      = slugify(title)
    filename  = f"{date_str}-{source}-{short_id}.md"
    filepath  = POSTS_DIR / filename

    if filepath.exists():
        return False   # already there

    tags_str = ", ".join(tags or [source])
    excerpt  = textwrap.shorten(content, width=200, placeholder="…")

    body = (
        frontmatter(
            layout    = "single",
            title     = title,
            date      = date.isoformat(),
            categories= source,
            tags      = tags_str,
            excerpt   = excerpt,
            source    = source,
            source_url= url,
        )
        + f"{content}\n\n"
        + (f"[View original post]({url}){{:target=\"_blank\"}}\n" if url else "")
    )

    filepath.write_text(body, encoding="utf-8")
    print(f"  [new] {filename}")
    return True


# ── Mastodon ──────────────────────────────────────────────────────────────────

def fetch_mastodon():
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        return 0

    print(f"\n── Mastodon (@{MASTODON_USERNAME}@{MASTODON_INSTANCE}) ──")

    # Look up account ID
    try:
        r = requests.get(
            f"https://{MASTODON_INSTANCE}/api/v1/accounts/lookup",
            params={"acct": MASTODON_USERNAME},
            timeout=15
        )
        r.raise_for_status()
        account_id = r.json()["id"]
    except Exception as e:
        print(f"  ERROR: could not look up account — {e}")
        return 0

    # Fetch public statuses
    try:
        r = requests.get(
            f"https://{MASTODON_INSTANCE}/api/v1/accounts/{account_id}/statuses",
            params={
                "limit": MAX_POSTS_PER_SOURCE,
                "exclude_replies": "true",
                "exclude_reblogs": "true",
            },
            timeout=20
        )
        r.raise_for_status()
        statuses = r.json()
    except Exception as e:
        print(f"  ERROR: could not fetch statuses — {e}")
        return 0

    seen = existing_post_ids("mastodon")
    new_count = 0

    for status in statuses:
        sid     = str(status.get("id", ""))
        raw_html = status.get("content", "")
        content  = strip_html(raw_html)

        if len(content) < MIN_CONTENT_LENGTH:
            continue
        if hashlib.md5(sid.encode()).hexdigest()[:10] in seen:
            continue

        created_at = status.get("created_at", "")
        try:
            date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            date = datetime.now(tz=timezone.utc)

        # Build title from first line of content
        first_line = content.split("\n")[0]
        title = textwrap.shorten(first_line, width=70, placeholder="…")
        if not title:
            title = f"Mastodon post {date.strftime('%Y-%m-%d')}"

        # Extract hashtags as tags
        tags = [t["name"] for t in status.get("tags", [])]
        tags = ["mastodon"] + tags[:5]

        url = status.get("url", "")
        wrote = write_post(date, "mastodon", sid, title, content, url, tags)
        if wrote:
            new_count += 1

    print(f"  Done — {new_count} new Mastodon posts.")
    return new_count


# ── LinkedIn (via RSS) ────────────────────────────────────────────────────────

def fetch_linkedin_rss():
    if not LINKEDIN_RSS_URL:
        print("\n── LinkedIn: LINKEDIN_RSS_URL not set, skipping. ──")
        print("   → Set it as a GitHub Actions secret and env var.")
        return 0

    try:
        import feedparser
    except ImportError:
        print("ERROR: feedparser not installed. Run: pip install feedparser")
        return 0

    print(f"\n── LinkedIn (RSS) ──")

    feed = feedparser.parse(LINKEDIN_RSS_URL)
    if not feed.entries:
        print("  No entries found or RSS feed is empty.")
        return 0

    seen = existing_post_ids("linkedin")
    new_count = 0

    for entry in feed.entries[:MAX_POSTS_PER_SOURCE]:
        uid     = entry.get("id") or entry.get("link") or ""
        title   = entry.get("title", "LinkedIn post").strip()
        content = strip_html(entry.get("summary") or entry.get("content", [{}])[0].get("value", ""))
        url     = entry.get("link", "")

        if len(content) < MIN_CONTENT_LENGTH:
            content = title  # use title as content if summary is empty

        if not title or title == "LinkedIn post":
            title = textwrap.shorten(content, width=70, placeholder="…") or "LinkedIn post"

        pub = entry.get("published_parsed") or entry.get("updated_parsed")
        if pub:
            date = datetime(*pub[:6], tzinfo=timezone.utc)
        else:
            date = datetime.now(tz=timezone.utc)

        uid_hash = hashlib.md5(uid.encode()).hexdigest()[:10]
        if uid_hash in seen:
            continue

        tags = ["linkedin"] + [t.get("term", "") for t in entry.get("tags", [])][:4]
        wrote = write_post(date, "linkedin", uid, title, content, url, tags)
        if wrote:
            new_count += 1

    print(f"  Done — {new_count} new LinkedIn posts.")
    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    POSTS_DIR.mkdir(exist_ok=True)
    total = 0
    total += fetch_mastodon()
    total += fetch_linkedin_rss()
    print(f"\n✓ Total new posts: {total}")
    sys.exit(0)
