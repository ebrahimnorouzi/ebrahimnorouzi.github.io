#!/usr/bin/env python3
"""
Import Instagram export images into the Jekyll gallery from Google Drive.

This script downloads a shared Google Drive folder that contains an Instagram
data export (or a plain folder of images) and:
  1. Copies images to images/gallery/
  2. Updates _data/gallery.yml with entries
  3. Optionally posts each image to Bluesky (requires BLUESKY_HANDLE + BLUESKY_APP_PASSWORD)

The Google Drive folder URL MUST be provided via the GDRIVE_INSTAGRAM_EXPORT_URL
environment variable (set it as a secret). Without it the script exits with an
error — there is no other way to point it at a source.

Instagram Export Structure (from "Download Your Information"):
  <gdrive folder>/
    media/posts/YYYYMMDD/
      *.jpg
    content/posts_1.json   (captions, dates, etc.)

Plain folder of images also works (captions.json optional).

Usage:
    export GDRIVE_INSTAGRAM_EXPORT_URL="https://drive.google.com/drive/folders/<id>?usp=sharing"
    python scripts/import_gallery.py

    # preview without writing
    python scripts/import_gallery.py --dry-run

    # also post to Bluesky
    python scripts/import_gallery.py --post-bluesky

Dependencies:
    pip install gdown requests pyyaml pillow
"""

import os
import re
import sys
import json
import shutil
import hashlib
import tempfile
import argparse
from datetime import datetime, timezone
from pathlib import Path

GALLERY_IMG_DIR = Path("images/gallery")
DATA_DIR = Path("_data")
GALLERY_YML = DATA_DIR / "gallery.yml"
MAX_IMAGE_WIDTH = 1600  # resize large images for web
GDRIVE_ENV_VAR = "GDRIVE_INSTAGRAM_EXPORT_URL"


def load_existing_gallery():
    """Load existing gallery.yml entries."""
    import yaml

    if not GALLERY_YML.exists():
        return []
    with open(GALLERY_YML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


def save_gallery(entries):
    """Write gallery entries to gallery.yml."""
    import yaml

    DATA_DIR.mkdir(exist_ok=True)
    with open(GALLERY_YML, "w", encoding="utf-8") as f:
        yaml.dump(entries, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  Wrote {len(entries)} entries to {GALLERY_YML}")


def copy_and_resize_image(src: Path, dest_name: str) -> str:
    """Copy image to gallery dir, optionally resizing. Returns filename."""
    GALLERY_IMG_DIR.mkdir(parents=True, exist_ok=True)
    dest = GALLERY_IMG_DIR / dest_name

    if dest.exists():
        print(f"  [skip] {dest_name} already exists")
        return dest_name

    try:
        from PIL import Image
        img = Image.open(src)
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        # Convert to RGB if necessary (e.g., RGBA PNGs)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=85, optimize=True)
        print(f"  [copy+resize] {dest_name}")
    except ImportError:
        # Pillow not installed — just copy
        shutil.copy2(src, dest)
        print(f"  [copy] {dest_name}")

    return dest_name


def parse_instagram_export(export_dir: Path):
    """Parse Instagram data export and return list of (image_path, caption, date, category)."""
    items = []

    # Look for posts JSON
    content_dir = export_dir / "content"
    posts_json = None
    for candidate in ["posts_1.json", "posts.json"]:
        p = content_dir / candidate
        if p.exists():
            posts_json = p
            break

    # Also check in your_instagram_activity/content/
    if not posts_json:
        for candidate in export_dir.rglob("posts_1.json"):
            posts_json = candidate
            break

    caption_map = {}  # media path -> caption, date
    if posts_json:
        print(f"  Found posts JSON: {posts_json}")
        with open(posts_json, encoding="utf-8") as f:
            data = json.load(f)

        posts = data if isinstance(data, list) else data.get("ig_posts", data.get("posts", []))
        for post in posts:
            media_list = post.get("media", [post])
            for media in media_list:
                uri = media.get("uri", "")
                caption = media.get("title", "")
                ts = media.get("creation_timestamp") or media.get("taken_at_timestamp")
                date = ""
                if ts:
                    date = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
                if uri:
                    caption_map[uri] = {"caption": caption, "date": date}

    # Find all images
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
    media_dirs = [export_dir / "media", export_dir / "photos", export_dir]

    for media_dir in media_dirs:
        if not media_dir.exists():
            continue
        for img_path in sorted(media_dir.rglob("*")):
            if img_path.suffix.lower() not in image_exts:
                continue
            if img_path.is_file():
                rel = str(img_path.relative_to(export_dir))
                info = caption_map.get(rel, {})
                caption = info.get("caption", "")
                date = info.get("date", "")

                # Try to extract date from directory name (YYYYMMDD)
                if not date:
                    m = re.search(r"(\d{4})(\d{2})(\d{2})", img_path.parent.name)
                    if m:
                        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                items.append({
                    "path": img_path,
                    "caption": caption,
                    "date": date,
                    "category": "Instagram",
                })

    return items


def parse_folder(folder: Path):
    """Parse a plain folder of images. Optional captions.json for metadata."""
    items = []
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

    # Check for captions file
    captions_file = folder / "captions.json"
    caption_map = {}
    if captions_file.exists():
        with open(captions_file, encoding="utf-8") as f:
            caption_map = json.load(f)
        print(f"  Found captions.json with {len(caption_map)} entries")

    for img_path in sorted(folder.rglob("*")):
        if img_path.suffix.lower() not in image_exts:
            continue
        if img_path.is_file():
            name = img_path.name
            info = caption_map.get(name, {})
            caption = info.get("caption", "") if isinstance(info, dict) else str(info)
            date = info.get("date", "") if isinstance(info, dict) else ""

            # Try to infer category from subdirectory
            rel_parent = img_path.parent.relative_to(folder)
            category = str(rel_parent) if str(rel_parent) != "." else "Gallery"
            category = category.replace("_", " ").replace("-", " ").title()

            items.append({
                "path": img_path,
                "caption": caption or name.rsplit(".", 1)[0].replace("_", " ").replace("-", " "),
                "date": date,
                "category": category,
            })

    return items


def post_to_bluesky(image_path: Path, caption: str):
    """Post an image to Bluesky using AT Protocol."""
    import requests

    handle = os.getenv("BLUESKY_HANDLE", "")
    app_password = os.getenv("BLUESKY_APP_PASSWORD", "")

    if not handle or not app_password:
        print("  SKIP Bluesky post: missing BLUESKY_HANDLE or BLUESKY_APP_PASSWORD")
        return False

    pds = "https://bsky.social"

    # Create session
    try:
        r = requests.post(f"{pds}/xrpc/com.atproto.server.createSession", json={
            "identifier": handle,
            "password": app_password,
        }, timeout=15)
        r.raise_for_status()
        session = r.json()
        access_token = session["accessJwt"]
        did = session["did"]
    except Exception as e:
        print(f"  ERROR Bluesky auth: {e}")
        return False

    headers = {"Authorization": f"Bearer {access_token}"}

    # Upload image blob
    try:
        mime = "image/jpeg"
        if image_path.suffix.lower() == ".png":
            mime = "image/png"
        with open(image_path, "rb") as f:
            img_data = f.read()

        r = requests.post(
            f"{pds}/xrpc/com.atproto.repo.uploadBlob",
            headers={**headers, "Content-Type": mime},
            data=img_data,
            timeout=30,
        )
        r.raise_for_status()
        blob = r.json()["blob"]
    except Exception as e:
        print(f"  ERROR uploading image: {e}")
        return False

    # Create post with image
    try:
        now = datetime.now(tz=timezone.utc).isoformat()
        record = {
            "$type": "app.bsky.feed.post",
            "text": caption[:300] if caption else "",
            "createdAt": now,
            "embed": {
                "$type": "app.bsky.embed.images",
                "images": [{
                    "alt": caption[:1000] if caption else "Gallery image",
                    "image": blob,
                }],
            },
        }

        r = requests.post(f"{pds}/xrpc/com.atproto.repo.createRecord", headers=headers, json={
            "repo": did,
            "collection": "app.bsky.feed.post",
            "record": record,
        }, timeout=15)
        r.raise_for_status()
        uri = r.json().get("uri", "")
        print(f"  [bluesky] Posted: {uri}")
        return True
    except Exception as e:
        print(f"  ERROR creating post: {e}")
        return False


def download_gdrive_folder(url: str, dest: Path) -> Path:
    """Download a publicly-shared Google Drive folder to `dest`.

    Requires the `gdown` package. The folder must be shared with
    "Anyone with the link can view" for this to work without auth.
    """
    try:
        import gdown
    except ImportError:
        print("  ERROR: gdown is not installed. Run: pip install gdown")
        raise

    dest.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading Google Drive folder...")
    print(f"    url → {url}")
    print(f"    dest → {dest}")

    gdown.download_folder(
        url=url,
        output=str(dest),
        quiet=False,
        use_cookies=False,
        remaining_ok=True,
    )
    return dest


def resolve_export_root(tmp_dir: Path) -> Path:
    """If gdown downloaded into a single subdirectory, descend into it."""
    entries = [p for p in tmp_dir.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return tmp_dir


def main():
    parser = argparse.ArgumentParser(
        description="Import Instagram export from Google Drive into the Jekyll gallery"
    )
    parser.add_argument("--category", default="", help="Override category for all images")
    parser.add_argument("--post-bluesky", action="store_true",
                        help="Also post each image to Bluesky")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    # Gallery is driven ONLY by the secret env var — no local-path fallback.
    gdrive_url = os.getenv(GDRIVE_ENV_VAR, "").strip()
    if not gdrive_url:
        print(f"ERROR: {GDRIVE_ENV_VAR} environment variable is not set.")
        print(f"       Set it to the shared link of the Google Drive folder that")
        print(f"       contains the Instagram export, then re-run. Example:")
        print(f"       export {GDRIVE_ENV_VAR}=\"https://drive.google.com/drive/folders/<id>?usp=sharing\"")
        sys.exit(1)

    print(f"\n── Import Gallery (Google Drive) ──")

    with tempfile.TemporaryDirectory(prefix="ig-export-") as tmp:
        tmp_path = Path(tmp)
        try:
            download_gdrive_folder(gdrive_url, tmp_path)
        except Exception as e:
            print(f"  ERROR downloading Google Drive folder: {e}")
            sys.exit(1)

        input_dir = resolve_export_root(tmp_path)

        # Try Instagram export structure first; fall back to a plain folder of images.
        items = parse_instagram_export(input_dir)
        if not items:
            print("  No Instagram export structure found — parsing as plain folder.")
            items = parse_folder(input_dir)

        print(f"  Found {len(items)} images")

        if not items:
            print("  No images found.")
            sys.exit(0)

        if args.dry_run:
            for item in items:
                cat = args.category or item["category"]
                print(f"  [dry-run] {item['path'].name} → {cat}: {item['caption'][:60]}")
            sys.exit(0)

        # Load existing gallery
        existing = load_existing_gallery()
        existing_images = {e.get("image", "") for e in existing if isinstance(e, dict)}

        new_count = 0
        for item in items:
            # Generate unique filename
            img_hash = hashlib.md5(item["path"].read_bytes()[:4096]).hexdigest()[:8]
            ext = item["path"].suffix.lower()
            if ext in (".heic", ".webp"):
                ext = ".jpg"
            dest_name = f"{img_hash}{ext}"

            if dest_name in existing_images:
                print(f"  [skip] {item['path'].name} already in gallery")
                continue

            # Copy image
            gallery_img = copy_and_resize_image(item["path"], dest_name)

            # Add to gallery data
            cat = args.category or item["category"]
            entry = {
                "category": cat,
                "image": gallery_img,
                "caption": item["caption"],
            }
            if item["date"]:
                entry["date"] = item["date"]

            existing.append(entry)
            existing_images.add(dest_name)
            new_count += 1

            # Post to Bluesky if requested
            if args.post_bluesky:
                dest_path = GALLERY_IMG_DIR / dest_name
                post_to_bluesky(dest_path, item["caption"])

        # Save updated gallery
        save_gallery(existing)
        print(f"\n✓ Imported {new_count} new images into gallery.")


if __name__ == "__main__":
    main()
