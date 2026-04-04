#!/usr/bin/env python3
"""
Fetch posts from Bluesky (AT Protocol) and create Jekyll _posts files.

Bluesky's public API requires no authentication for reading public profiles.

Usage:
    python scripts/fetch_bluesky_posts.py

Dependencies:
    pip install requests

Configuration (env vars or edit CONFIG below):
    BLUESKY_HANDLE  — e.g. norouzi-iut.bsky.social
    MAX_POSTS       — max posts to fetch per run (default 30)
    INCLUDE_REPOSTS — include reposts/quotes (default true)
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
BLUESKY_HANDLE       = os.getenv("BLUESKY_HANDLE", "norouzi-iut.bsky.social")
BLUESKY_API          = "https://public.api.bsky.app"
MAX_POSTS            = int(os.getenv("MAX_POSTS", "30"))
INCLUDE_REPOSTS      = os.getenv("INCLUDE_REPOSTS", "true").lower() == "true"
POSTS_DIR            = Path("_posts")
MIN_CONTENT_LENGTH   = 30
# ─────────────────────────────────────────────────────────────────────────────


# ── Helpers (shared with fetch_social_posts.py) ──────────────────────────────

def slugify(text: str, maxlen: int = 50) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:maxlen].strip("-")


def strip_html(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</p>", "\n\n", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def frontmatter(**kv) -> str:
    lines = ["---"]
    for k, v in kv.items():
        v_str = str(v).replace('"', '\\"').replace("'", "&#39;")
        lines.append(f'{k}: "{v_str}"')
    lines.append("---\n")
    return "\n".join(lines)


def existing_post_ids(source: str) -> set:
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
    date_str = date.strftime("%Y-%m-%d")
    filename = f"{date_str}-{source}-{short_id}.md"
    filepath = POSTS_DIR / filename

    if filepath.exists():
        return False

    tags_str = ", ".join(tags or [source])
    excerpt = textwrap.shorten(content, width=200, placeholder="…")

    body = (
        frontmatter(
            layout="single",
            title=title,
            date=date.isoformat(),
            categories=source,
            tags=tags_str,
            excerpt=excerpt,
            source=source,
            source_url=url,
        )
        + f"{content}\n\n"
        + (f"[View original post]({url}){{:target=\"_blank\"}}\n" if url else "")
    )

    filepath.write_text(body, encoding="utf-8")
    print(f"  [new] {filename}")
    return True


# ── Bluesky ──────────────────────────────────────────────────────────────────

def resolve_handle(handle: str) -> str:
    """Resolve a Bluesky handle to a DID."""
    import requests

    r = requests.get(
        f"{BLUESKY_API}/xrpc/com.atproto.identity.resolveHandle",
        params={"handle": handle},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["did"]


def post_url(handle: str, uri: str) -> str:
    """Convert an AT URI to a bsky.app web URL."""
    # at://did:plc:xxx/app.bsky.feed.post/rkey -> https://bsky.app/profile/handle/post/rkey
    parts = uri.split("/")
    rkey = parts[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def extract_text_from_record(record: dict) -> str:
    """Extract plain text from a Bluesky post record, resolving facets/links."""
    text = record.get("text", "")
    return text.strip()


def fetch_bluesky():
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        return 0

    print(f"\n── Bluesky (@{BLUESKY_HANDLE}) ──")

    # Resolve handle to DID
    try:
        did = resolve_handle(BLUESKY_HANDLE)
        print(f"  Resolved {BLUESKY_HANDLE} → {did}")
    except Exception as e:
        print(f"  ERROR: could not resolve handle — {e}")
        return 0

    # Fetch author feed
    try:
        params = {
            "actor": did,
            "limit": MAX_POSTS,
            "filter": "posts_and_author_threads",
        }
        if not INCLUDE_REPOSTS:
            params["filter"] = "posts_no_replies"

        r = requests.get(
            f"{BLUESKY_API}/xrpc/app.bsky.feed.getAuthorFeed",
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        feed = r.json().get("feed", [])
    except Exception as e:
        print(f"  ERROR: could not fetch feed — {e}")
        return 0

    seen = existing_post_ids("bluesky")
    new_count = 0

    for item in feed:
        post_data = item.get("post", {})
        record = post_data.get("record", {})
        uri = post_data.get("uri", "")
        cid = post_data.get("cid", "")

        if not uri or not record:
            continue

        # Use CID as unique identifier
        uid = cid or uri
        if hashlib.md5(uid.encode()).hexdigest()[:10] in seen:
            continue

        # Check if this is a repost
        reason = item.get("reason", {})
        is_repost = reason.get("$type") == "app.bsky.feed.defs#reasonRepost"

        # Get content
        content = extract_text_from_record(record)

        # Handle quote posts — append quoted text
        embed = record.get("embed", {})
        if embed.get("$type") == "app.bsky.embed.record":
            quoted_record = embed.get("record", {})
            quoted_uri = quoted_record.get("uri", "")
            # We just note it's a quote — the quoted content would need another API call
            if quoted_uri:
                content += "\n\n*(Quote post)*"

        # Handle reposts
        if is_repost:
            repost_author = post_data.get("author", {}).get("handle", "")
            repost_display = post_data.get("author", {}).get("displayName", repost_author)
            url = post_url(repost_author, uri)
        else:
            url = post_url(BLUESKY_HANDLE, uri)

        if len(content) < MIN_CONTENT_LENGTH:
            continue

        # Parse date
        created_at = record.get("createdAt", "")
        try:
            date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            print(f"  SKIP: unparseable date — {created_at!r}")
            continue

        # Build title
        first_line = content.split("\n")[0]
        title = textwrap.shorten(first_line, width=70, placeholder="…")

        if is_repost:
            repost_author = post_data.get("author", {}).get("handle", "")
            if not title:
                title = f"Repost from @{repost_author} — {date.strftime('%Y-%m-%d')}"
            else:
                title = f"Repost: {title}"
            content = f"*Reposted from [@{repost_author}]({url})*\n\n{content}"
            tags = ["bluesky", "repost"]
        else:
            if not title:
                title = f"Bluesky post {date.strftime('%Y-%m-%d')}"
            tags = ["bluesky"]

        # Extract hashtags from facets
        facets = record.get("facets", [])
        for facet in facets:
            for feature in facet.get("features", []):
                if feature.get("$type") == "app.bsky.richtext.facet#tag":
                    tag_name = feature.get("tag", "")
                    if tag_name and tag_name not in tags:
                        tags.append(tag_name)

        tags = tags[:7]  # limit tags

        wrote = write_post(date, "bluesky", uid, title, content, url, tags)
        if wrote:
            new_count += 1

    print(f"  Done — {new_count} new Bluesky posts.")
    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    POSTS_DIR.mkdir(exist_ok=True)
    total = fetch_bluesky()
    print(f"\n✓ Total new posts: {total}")
    sys.exit(0)
