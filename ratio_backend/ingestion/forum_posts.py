"""Forum ingestion helpers for collecting all WebsiteToolbox posts for a ticker."""

import asyncio
import os
import json
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import httpx

from ..core.config import get_settings

# Load environment variables from .env
load_dotenv()

WEBSITETOOLBOX_API_KEY = os.getenv("WEBSITETOOLBOX_API_KEY")
FORUM_AUTHOR_EMAIL = (os.getenv("FORUM_AUTHOR_EMAIL") or "").strip().lower()

BASE_URL = "https://api.websitetoolbox.com/v1/api"

HEADERS = {
    "Accept": "application/json",
    "x-api-key": WEBSITETOOLBOX_API_KEY
}

MAX_RETRIES = 3
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 30.0
TOPIC_REQUEST_CONCURRENCY = 4
POST_REQUEST_CONCURRENCY = 2
BAD_REQUEST_RETRY_BASE_SECONDS = 1.0

# ---------------------------
# Low-level helpers
# ---------------------------

def _extract_author_email(post: dict) -> str:
    """
    WebsiteToolbox payloads can vary. Try a few common shapes.
    """
    # 1) current assumed shape
    author = post.get("author") or {}
    email = author.get("email")
    if email:
        return str(email)

    # 2) sometimes direct
    email = post.get("authorEmail")
    if email:
        return str(email)

    # 3) other possible shapes (defensive)
    user = post.get("user") or {}
    email = user.get("email")
    if email:
        return str(email)

    created_by = post.get("createdBy") or {}
    email = created_by.get("email")
    if email:
        return str(email)

    return ""


async def _request_with_retry_async(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    semaphore: asyncio.Semaphore,
):
    """Perform a bounded, rate-limited API request with retry/backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            async with semaphore:
                response = await client.get(url, params=params)

            if response.status_code == 400:
                body_text = response.text.lower()
                if "restricted" in body_text or "archived" in body_text:
                    return None
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BAD_REQUEST_RETRY_BASE_SECONDS * (attempt + 1))
                    continue
                return None

            response.raise_for_status()

            if not response.content:
                return None

            return response.json()

        except httpx.HTTPError as exc:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                print(f"Giving up on {url} params={params}: {exc}")
                return None


async def _paginate_async(
    client: httpx.AsyncClient,
    endpoint: str,
    base_params: dict,
    *,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch every page for an endpoint sequentially, returning a full item list."""
    items: list[dict] = []
    page = 1
    while True:
        params = dict(base_params)
        params["page"] = page
        params["pageSize"] = PAGE_SIZE

        data = await _request_with_retry_async(
            client,
            f"{BASE_URL}/{endpoint}",
            params,
            semaphore=semaphore,
        )
        if not data:
            break

        page_items = data.get("data", [])
        if not page_items:
            break

        items.extend(page_items)

        total = data.get("totalSize")
        if total is not None and page * PAGE_SIZE >= total:
            break

        page += 1

    return items


def _clean_html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    return soup.get_text(separator=" ").strip()


def _get_forum_author_email() -> str:
    """Return the configured forum author email or raise if it is missing."""
    if not FORUM_AUTHOR_EMAIL:
        raise ValueError("FORUM_AUTHOR_EMAIL not found in .env file")
    return FORUM_AUTHOR_EMAIL


# ---------------------------
# API wrappers
# ---------------------------

async def get_categories_async(
    client: httpx.AsyncClient,
    *,
    semaphore: asyncio.Semaphore,
):
    """Fetch all forum categories."""
    data = await _request_with_retry_async(
        client,
        f"{BASE_URL}/categories",
        {},
        semaphore=semaphore,
    )
    return data or {"data": []}


def get_subcategories(all_categories, parent_id):
    """
    Recursively collect all descendants under parent_id.
    """
    subcats = []
    for cat in all_categories.get("data", []):
        if cat.get("parentId") == parent_id:
            subcats.append(cat)
            subcats.extend(get_subcategories(all_categories, cat["categoryId"]))
    return subcats


async def get_topics_for_category_async(
    client: httpx.AsyncClient,
    category_id: int,
    *,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch all topics for a category."""
    return await _paginate_async(
        client,
        "topics",
        {"categoryId": category_id},
        semaphore=semaphore,
    )


async def get_posts_for_topic_async(
    client: httpx.AsyncClient,
    topic_id: int,
    *,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch all posts for a topic."""
    return await _paginate_async(
        client,
        "posts",
        {"topicId": topic_id},
        semaphore=semaphore,
    )


# ---------------------------
# Ticker config
# ---------------------------

def load_ticker_config():
    try:
        with open("forum_search_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_search_ticker(input_ticker, config):
    return config.get(input_ticker, input_ticker)


# ---------------------------
# Main pipeline
# ---------------------------

def _get_output_dir() -> Path:
    """Return the configured output directory for generated artifacts."""
    output_dir = get_settings().output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def collect_forum_posts_for_ticker_async(input_ticker):
    """Collect and normalize all forum posts for the configured ticker category tree."""
    forum_author_email = _get_forum_author_email()
    config = load_ticker_config()
    ticker = get_search_ticker(input_ticker, config)

    topic_semaphore = asyncio.Semaphore(TOPIC_REQUEST_CONCURRENCY)
    post_semaphore = asyncio.Semaphore(POST_REQUEST_CONCURRENCY)
    fallback_post_semaphore = asyncio.Semaphore(1)

    async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        all_categories = await get_categories_async(
            client,
            semaphore=topic_semaphore,
        )
        parent_cat = next(
            (category for category in all_categories.get("data", []) if category.get("title") == ticker),
            None,
        )

        if not parent_cat:
            print(f"No category found with title '{ticker}'.")
            return

        parent_id = parent_cat["categoryId"]
        print(f"Found category '{ticker}' (ID={parent_id}).")

        subcategories = get_subcategories(all_categories, parent_id)
        relevant_categories = [parent_cat] + subcategories

        seen_cat_ids = set()
        unique_categories = []
        for cat in relevant_categories:
            cid = cat["categoryId"]
            if cid not in seen_cat_ids:
                unique_categories.append(cat)
                seen_cat_ids.add(cid)

        unique_posts = {}
        seen_topics = set()

        category_tasks = [
            get_topics_for_category_async(
                client,
                cat["categoryId"],
                semaphore=topic_semaphore,
            )
            for cat in unique_categories
        ]
        category_topics = await asyncio.gather(*category_tasks)

        topic_requests: list[tuple[dict, dict]] = []
        for cat, topics in zip(unique_categories, category_topics):
            cat_id = cat["categoryId"]
            cat_title = cat["title"]

            print(f"Category '{cat_title}' (ID={cat_id}) -> {len(topics)} topic(s).")

            for topic in topics:
                topic_id = topic.get("topicId")
                if topic_id in seen_topics:
                    continue
                seen_topics.add(topic_id)
                topic_requests.append((cat, topic))

        topic_tasks = [
            get_posts_for_topic_async(
                client,
                topic["topicId"],
                semaphore=post_semaphore,
            )
            for _, topic in topic_requests
        ]
        topic_posts = await asyncio.gather(*topic_tasks)

        recovered_topic_posts: list[list[dict]] = []
        for (cat, topic), posts in zip(topic_requests, topic_posts):
            if posts:
                recovered_topic_posts.append(posts)
                continue

            topic_id = topic.get("topicId")
            recovered_posts = await get_posts_for_topic_async(
                client,
                topic_id,
                semaphore=fallback_post_semaphore,
            )
            recovered_topic_posts.append(recovered_posts)

        for (cat, topic), posts in zip(topic_requests, recovered_topic_posts):
            cat_id = cat["categoryId"]
            cat_title = cat["title"]
            topic_id = topic.get("topicId")
            topic_title = topic.get("title")

            print(f"  Topic '{topic_title}' (ID={topic_id}) -> {len(posts)} post(s).")

            for post in posts:
                author_email = _extract_author_email(post).strip().lower()
                if author_email != forum_author_email:
                    continue

                post_id = post.get("postId")
                if post_id not in unique_posts:
                    unique_posts[post_id] = {
                        "timestamp": post.get("postTimestamp", 0),
                        "message": _clean_html_to_text(post.get("message", "")),
                        "authorEmail": author_email,
                        "postId": post_id,
                        "topicId": topic_id,
                        "topicTitle": topic_title,
                        "categoryId": cat_id,
                        "categoryTitle": cat_title,
                    }

    simplified_posts = sorted(unique_posts.values(), key=lambda p: p["timestamp"])
    return {
        "ticker": ticker,
        "category": {"title": parent_cat.get("title"), "categoryId": parent_id},
        "posts": simplified_posts,
    }


def collect_forum_posts_for_ticker(input_ticker):
    """Synchronously collect forum posts using the async collector."""
    return asyncio.run(collect_forum_posts_for_ticker_async(input_ticker))


def write_forum_posts_snapshot(ticker: str, payload: dict, output_dir: Path | None = None) -> Path:
    """Write collected forum posts to the canonical JSON artifact."""
    target_dir = output_dir or _get_output_dir()
    output_path = target_dir / f"{ticker}_forum_posts.json"

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    return output_path


def fetch_all_for_ticker(input_ticker):
    """Collect all forum posts for a ticker and persist the normalized artifact."""
    payload = collect_forum_posts_for_ticker(input_ticker)
    if not payload:
        return None
    output_path = write_forum_posts_snapshot(payload["ticker"], payload)
    print(f"Saved {len(payload['posts'])} posts to '{output_path}'.")
    return payload


# ---------------------------
# CLI
# ---------------------------

def _print_cli_usage():
    print(
        "Usage:\n"
        "  python -m ratio_backend.ingestion.forum_posts TICKER\n"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        _print_cli_usage()
        sys.exit(1)

    input_ticker = sys.argv[1]
    fetch_all_for_ticker(input_ticker)
