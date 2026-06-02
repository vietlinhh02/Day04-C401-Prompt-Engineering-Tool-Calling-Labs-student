from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, apify_run, err, tweet_item


def _rapid_search(query: str, search_type: str, limit: int) -> dict[str, Any]:
    key = os.getenv("RAPIDAPI_KEY")
    host = os.getenv("RAPIDAPI_TWITTER_HOST", "twitter241.p.rapidapi.com")
    if not key:
        raise RuntimeError("Missing RAPIDAPI_KEY env var")
    resp = requests.get(
        f"https://{host}/search.php",
        params={"query": query, "search_type": search_type},
        headers={"x-rapidapi-key": key, "x-rapidapi-host": host},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_items = data.get("timeline") or data.get("tweets") or []
    items = [tweet_item(item) for item in raw_items if item.get("tweet_id") or item.get("id")]
    return {"tool": "search_tweets", "query": query, "search_type": search_type, "items": items[:limit]}


def _apify_search(query: str, search_type: str, limit: int) -> dict[str, Any]:
    search_type_map = {"Latest": "latest", "Top": "top"}
    raw_items = apify_run("scrapium/x-twitter-posts-search", {
        "startUrls": [f"search: {query}"],
        "maxTweets": limit,
        "searchType": search_type_map.get(search_type, "latest"),
    })
    items = [tweet_item(item) for item in raw_items[:limit]]
    return {"tool": "search_tweets", "query": query, "search_type": search_type, "items": items}


def search_tweets(query: str = "", search_type: str = "Latest", limit: int = 5) -> dict[str, Any]:
    try:
        if not query:
            return {"tool": "search_tweets", "error": "missing_query", "message": "Query is required"}
        try:
            return _apify_search(query, search_type, limit)
        except Exception:
            return _rapid_search(query, search_type, limit)
    except Exception as exc:
        return err("search_tweets", exc)
