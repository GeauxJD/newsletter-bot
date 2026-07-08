"""
Newsletter aggregation - fetch stage.

Reads sources.yml, pulls content from public Google Docs and GitHub
releases, and writes a normalized JSON file for the generation stage.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
import yaml

MIN_DOC_LENGTH = 50  # a "successful" fetch shorter than this is treated as a failure


def fetch_google_doc(doc_id: str, retries: int = 4, timeout: int = 45) -> str:
    """
    Fetch plain-text content of a publicly viewable Google Doc.

    Retries on timeouts AND on suspiciously short/empty "successful"
    responses, since this endpoint has been observed to occasionally
    return HTTP 200 with a truncated or empty body.
    """
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            text = resp.text

            if "accounts.google.com" in resp.url or "<html" in text.lower()[:200]:
                raise RuntimeError(
                    f"Doc {doc_id} returned an HTML/login page instead of "
                    "text - check that it's shared as 'Anyone with the link'."
                )

            if len(text.strip()) < MIN_DOC_LENGTH:
                raise RuntimeError(
                    f"Doc {doc_id} returned only {len(text.strip())} chars - "
                    "treating as a truncated/failed fetch, not real content."
                )

            return text.strip()

        except (requests.exceptions.Timeout, RuntimeError) as e:
            last_error = e
            print(f"  [retry {attempt}/{retries}] {e}")
            time.sleep(2 * attempt)  # small backoff between attempts

    raise RuntimeError(
        f"Doc {doc_id} failed after {retries} attempts. Last error: {last_error}"
    )


def fetch_github_releases(owner: str, repo: str, max_releases: int = 3) -> list:
    """Fetch the most recent releases for a repo via the GitHub REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {"Accept": "application/vnd.github+json"}

    resp = requests.get(url, headers=headers, params={"per_page": max_releases}, timeout=15)
    resp.raise_for_status()
    releases = resp.json()

    return [
        {
            "tag": r["tag_name"],
            "name": r.get("name") or r["tag_name"],
            "published_at": r["published_at"],
            "body": r.get("body") or "",
            "url": r["html_url"],
        }
        for r in releases
    ]


def build_aggregate(config: dict) -> list:
    aggregate = []

    for src in config.get("google_docs", []):
        try:
            content = fetch_google_doc(src["doc_id"])
            aggregate.append({
                "source_type": "meeting_notes",
                "source_name": src["name"],
                "date": datetime.now(timezone.utc).date().isoformat(),
                "content": content,
            })
        except Exception as e:
            print(f"[warn] failed to fetch doc '{src.get('name')}': {e}")

    for src in config.get("github_repos", []):
        try:
            releases = fetch_github_releases(
                src["owner"], src["repo"], src.get("max_releases", 3)
            )
            for rel in releases:
                aggregate.append({
                    "source_type": "release",
                    "source_name": src["name"],
                    "date": rel["published_at"][:10],
                    "content": f"{rel['name']} ({rel['tag']})\n{rel['body']}",
                    "url": rel["url"],
                })
        except Exception as e:
            print(f"[warn] failed to fetch releases for '{src.get('name')}': {e}")

    return aggregate


if __name__ == "__main__":
    with open("sources.yml") as f:
        config = yaml.safe_load(f)

    data = build_aggregate(config)

    print(f"\nCollected {len(data)} items:\n")
    for item in data:
        preview = re.sub(r"\s+", " ", item["content"])[:120]
        print(f"- [{item['source_type']}] {item['source_name']} ({item['date']}): {preview}...")

    if not data:
        print("\nNo content fetched at all - failing so this doesn't silently produce an empty newsletter.")
        sys.exit(1)

    with open("aggregate.json", "w") as f:
        json.dump(data, f, indent=2)
