from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, apify_run, err, tweet_item


def _rapid_timeline(screenname: str, limit: int) -> dict[str, Any]:
    key = os.getenv("RAPIDAPI_KEY")
    host = os.getenv("RAPIDAPI_TWITTER_HOST", "twitter241.p.rapidapi.com")
    if not key:
        raise RuntimeError("Missing RAPIDAPI_KEY env var")
    resp = requests.get(
        f"https://{host}/timeline.php",
        params={"screenname": screenname},
        headers={"x-rapidapi-key": key, "x-rapidapi-host": host},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    raw_items = data.get("timeline") or data.get("tweets") or []
    items = [tweet_item(item) for item in raw_items if item.get("tweet_id") or item.get("id")]
    return {"tool": "get_user_tweets", "screenname": screenname, "items": items[:limit]}


def _apify_timeline(screenname: str, limit: int) -> dict[str, Any]:
    raw_items = apify_run("scrapium/x-twitter-posts-search", {
        "startUrls": [f"https://x.com/{screenname}"],
        "maxTweets": limit,
        "searchType": "latest",
    })
    items = [tweet_item(item) for item in raw_items[:limit]]
    return {"tool": "get_user_tweets", "screenname": screenname, "items": items}


def get_user_tweets(screenname: str = "", limit: int = 5) -> dict[str, Any]:
    try:
        if not screenname:
            return {"tool": "get_user_tweets", "error": "missing_screenname", "message": "Screenname is required"}
        try:
            return _apify_timeline(screenname, limit)
        except Exception:
            return _rapid_timeline(screenname, limit)
    except Exception as exc:
        return err("get_user_tweets", exc)
