#!/usr/bin/env python3
"""
Fetch posts from Mastodon and create Jekyll _posts files.

Usage:
    python scripts/fetch_social_posts.py

Dependencies:
    pip install requests beautifulsoup4

Configuration (edit the CONFIG block below or pass as env vars):
    MASTODON_INSTANCE  — e.g. sigmoid.social
    MASTODON_USERNAME  — e.g. enorouzi
    MAX_POSTS_PER_SOURCE — max posts to import per run
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
MAX_POSTS_PER_SOURCE   = int(os.getenv("MAX_POSTS",       "20"))
INCLUDE_BOOSTS         = os.getenv("INCLUDE_BOOSTS", "true").lower() == "true"
POSTS_DIR              = Path("_posts")
MIN_CONTENT_LENGTH     = 30   # skip very short toots
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

    # Fetch public statuses (including boosts if enabled)
    print(f"  Including boosts: {INCLUDE_BOOSTS}")
    try:
        r = requests.get(
            f"https://{MASTODON_INSTANCE}/api/v1/accounts/{account_id}/statuses",
            params={
                "limit": MAX_POSTS_PER_SOURCE,
                "exclude_replies": "true",
                "exclude_reblogs": "false" if INCLUDE_BOOSTS else "true",
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
        sid = str(status.get("id", ""))
        if hashlib.md5(sid.encode()).hexdigest()[:10] in seen:
            continue

        # Boosts (reblogs) carry content inside status["reblog"]
        is_boost = status.get("reblog") is not None
        if is_boost:
            reblog         = status["reblog"]
            raw_html       = reblog.get("content", "")
            content        = strip_html(raw_html)
            boosted_author = reblog.get("account", {}).get("acct", "")
            # Use the original post's URL (not the /activity reblog endpoint)
            boost_url      = reblog.get("url", "")
            # Use the original post's publication date, not the boost action date
            created_at     = reblog.get("created_at", "") or status.get("created_at", "")
        else:
            raw_html       = status.get("content", "")
            content        = strip_html(raw_html)
            boosted_author = ""
            boost_url      = ""
            created_at     = status.get("created_at", "")
        try:
            date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            date = datetime.now(tz=timezone.utc)

        # Build title
        first_line = content.split("\n")[0]
        title = textwrap.shorten(first_line, width=70, placeholder="…")
        if is_boost:
            if not title:
                title = f"Boost from @{boosted_author} — {date.strftime('%Y-%m-%d')}"
            else:
                title = f"Boost: {title}"
        elif not title:
            title = f"Mastodon post {date.strftime('%Y-%m-%d')}"

        # Tags
        source_status = status["reblog"] if is_boost else status
        tags = [t["name"] for t in source_status.get("tags", [])]
        tags = (["mastodon", "boost"] if is_boost else ["mastodon"]) + tags[:5]

        # For boosts, link to the original post; for own posts use the status URL
        url = boost_url if is_boost else status.get("url", "")
        if is_boost and boosted_author:
            content = f"*Boosted from [@{boosted_author}]({boost_url})*\n\n{content}"

        wrote = write_post(date, "mastodon", sid, title, content, url, tags)
        if wrote:
            new_count += 1

    print(f"  Done — {new_count} new Mastodon posts.")
    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    POSTS_DIR.mkdir(exist_ok=True)
    total = fetch_mastodon()
    print(f"\n✓ Total new posts: {total}")
    sys.exit(0)
