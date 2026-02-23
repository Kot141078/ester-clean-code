# -*- coding: utf-8 -*-
"""
X Trends Search: Poisk trendov na X (Twitter).
Novyy: Dobavlen s ispolzovaniem Twitter API (simulyatsiya s requests).
"""
from typing import Any, Dict, List
import os

import requests

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")


def get_bearer_token() -> str:
    """
    Vozvraschaet bearer token.
    Prioritet:
      1) TWITTER_BEARER_TOKEN env
      2) OAuth2 client credentials (TWITTER_API_KEY/SECRET)
    """
    env_token = os.getenv("TWITTER_BEARER_TOKEN", "").strip()
    if env_token:
        return env_token
    if not TWITTER_API_KEY or not TWITTER_API_SECRET:
        return ""
    try:
        import base64
        creds = f"{TWITTER_API_KEY}:{TWITTER_API_SECRET}".encode("utf-8")
        b64 = base64.b64encode(creds).decode("utf-8")
        headers = {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        }
        data = {"grant_type": "client_credentials"}
        r = requests.post("https://api.twitter.com/oauth2/token", headers=headers, data=data, timeout=15)
        r.raise_for_status()
        token = r.json().get("access_token", "")
        return token or ""
    except Exception:
        return ""


def search_trends(query: str) -> List[Dict[str, Any]]:
    bearer = get_bearer_token()
    if not bearer:
        return []
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer}"}
    params = {"query": query, "max_results": 10, "tweet.fields": "created_at,author_id"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", []) or []
        trends = [{"text": tweet.get("text", ""), "id": tweet.get("id", "")} for tweet in data]
        return [t for t in trends if t.get("text")]
    except Exception:
        return []
