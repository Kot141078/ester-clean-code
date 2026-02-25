# -*- coding: utf-8 -*-
from urllib.parse import urlparse

import requests

from config import GOOGLE_API_KEY, GOOGLE_CX
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def is_link_available(link):
    try:
        response = requests.head(link, timeout=5)
        return response.status_code < 400
    except:
        return False


def classify_link(link):
    domain = urlparse(link).netloc.lower()
    if any(keyword in domain for keyword in ["nature.com", "sciencedirect", "springer", "arxiv"]):
        return "nauchnyy"
    elif any(keyword in domain for keyword in ["bbc", "cnn", "news", "meduza", "ria"]):
        return "novostnoy"
    elif any(keyword in domain for keyword in ["reddit", "stackoverflow", "forum"]):
        return "forum"
    else:
        return "drugoe"


def google_search(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CX, "q": query, "num": 3}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("items", []):
            title = item.get("title")
            snippet = item.get("snippet")
            link = item.get("link")
            if is_link_available(link):
                typ = classify_link(link)
                results.append(f"[{typ}] {title}\n{snippet}\n{link}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Search error: ZZF0Z"
