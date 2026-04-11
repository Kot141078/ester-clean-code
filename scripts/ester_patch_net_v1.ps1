# ==============================
# Ester Patch v1.1: Net Bridge + Cache + Ingest (Complete)
# Author: Gemini (Architect) for Owner
#
# Changes:
# 1. net_bridge.py: Integrated user provided "Pure Search" logic.
# 2. net_cache.py: Added JSON-based caching (Cover & Thomas style) to reduce API noise.
# 3. html_extract.py: Added "Gray's" sanitizer (BS4 based) for clean text extraction.
# 4. net_manager.py: Orchestrator logic.
# ==============================

param(
  [string]$ProjectRoot = "<repo-root>"
)

$ErrorActionPreference = "Stop"

# --- HELPER FUNCTIONS ---
function Write-FileUtf8NoBom([string]$Path, [string]$Content) {
  $dir = Split-Path -Parent $Path
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Backup-File([string]$Path, [string]$Stamp) {
  if (Test-Path $Path) {
    $bak = "$Path.bak_$Stamp"
    Copy-Item -LiteralPath $Path -Destination $bak -Force
    return $bak
  }
  return $null
}

# --- MODULE CONTENT DEFINITIONS ---

# 1. net_bridge.py (User Provided - Pure Search Edition)
$code_net_bridge = @'
# -*- coding: utf-8 -*-
"""
modules/net_bridge.py - PURE SEARCH EDITION
Tolko poisk. Nikakikh popytok sokhraneniya v slomannyy vstore.
"""
import requests
import json
import os
import traceback

# Settings (take from ENV or hardcode for reliability)
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "c41e3c88410de59c14deb4bfa4707bddcb5dec61d6db3052d82780d7556f1e1e")

def google_search(query):
    """Realnyy poisk cherez SerpApi"""
    print(f"[NetBridge] 🔍 Google Search: {query}")
    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": 5,
            "hl": "ru"
        }
        resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
        data = resp.json()
        
        results = []
        # Organicheskie rezultaty
        if "organic_results" in data:
            for item in data["organic_results"]:
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet", "")
                })
        
        # Blok "Knowledge Graph" (esli est)
        if "knowledge_graph" in data:
            kg = data["knowledge_graph"]
            results.insert(0, {
                "title": kg.get("title", "Info"),
                "link": "",
                "snippet": kg.get("description", "")
            })

        return results
    except Exception as e:
        print(f"[NetBridge] ❌ Error: {e}")
        return []

def search(payload):
    """
    Edinaya tochka vkhoda.
    payload = {"q": "zapros"}
    """
    query = payload.get("q", "")
    if not query:
        return {"ok": False, "error": "No query"}

    try:
        # 1. Ischem
        items = google_search(query)
        
        return {
            "ok": True,
            "results": items,
            "count": len(items)
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
'@

# 2. net_cache.py (New - "Cover & Thomas" Layer)
$code_net_cache = @'
# -*- coding: utf-8 -*-
"""
modules/net_cache.py - Short-term memory for network requests.
Reduces noise and saves credits.
"""
import json
import os
import hashlib
import time

CACHE_FILE = "data/net_cache.json"
TTL_SECONDS = 86400  # 24 hours

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_cached(key_prefix, query):
    """Returns cached data if valid."""
    cache = load_cache()
    h = hashlib.md5(query.encode()).hexdigest()
    key = f"{key_prefix}:{h}"
    
    if key in cache:
        entry = cache[key]
        if time.time() - entry["ts"] < TTL_SECONDS:
            return entry["data"]
    return None

def set_cached(key_prefix, query, data):
    """Saves data to cache."""
    cache = load_cache()
    h = hashlib.md5(query.encode()).hexdigest()
    key = f"{key_prefix}:{h}"
    
    cache[key] = {
        "ts": time.time(),
        "data": data,
        "query": query
    }
    save_cache(cache)
'@

# 3. html_extract.py (New - "Gray's Anatomy" Layer)
$code_html_extract = @'
# -*- coding: utf-8 -*-
"""
modules/html_extract.py - Extracts clean text from raw HTML.
Dependency: pip install beautifulsoup4 requests
"""
import requests
from bs4 import BeautifulSoup
import re

def fetch_and_clean(url):
    """Downloads URL, strips boilerplates, returns clean text."""
    try:
        headers = {"User-Agent": "Ester/1.0 (SovereignNode)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Kill all script and style elements
        for script in soup(["script", "style", "nav", "footer", "iframe"]):
            script.decompose()
            
        text = soup.get_text(separator="\n")
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        return {"ok": True, "text": text, "title": soup.title.string if soup.title else url}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}
'@

# 4. net_manager.py (New - Orchestrator)
$code_net_manager = @'
# -*- coding: utf-8 -*-
"""
modules/net_manager.py - The Brain's interface to the Web.
Routes requests to cache or bridge.
"""
from modules import net_bridge, net_cache, html_extract

def search_internet(query, force=False):
    """
    Orchestrates search:
    1. Check Cache
    2. If miss, call Bridge
    3. Save to Cache
    """
    if not force:
        cached = net_cache.get_cached("search", query)
        if cached:
            print(f"[NetManager] 🟢 Cache Hit: {query}")
            return cached
            
    print(f"[NetManager] 🟠 Cache Miss. Calling Bridge...")
    result = net_bridge.search({"q": query})
    
    if result.get("ok"):
        net_cache.set_cached("search", query, result)
        
    return result

def ingest_url(url):
    """
    Fetches a specific URL, extracts text.
    Does NOT auto-save to memory (that's the Will's job).
    """
    print(f"[NetManager] 📥 Ingesting: {url}")
    return html_extract.fetch_and_clean(url)
'@

# 5. url_ingest.py (Stub for compatibility)
$code_url_ingest = @'
# -*- coding: utf-8 -*-
from modules.net_manager import ingest_url as fetch
# Alias wrapper
def process(url):
    return fetch(url)
'@

# 6. Routes (Fetch & Ingest)
$code_routes_fetch = @'
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from modules import net_manager

bp = Blueprint("net_fetch", __name__)

@bp.route("/net/search", methods=["POST"])
def net_search():
    """Endpoint for manual search request."""
    data = request.json
    query = data.get("q")
    if not query:
        return jsonify({"ok": False, "error": "No query"}), 400
        
    res = net_manager.search_internet(query)
    return jsonify(res)
'@

$code_routes_ingest = @'
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from modules import net_manager
import time
import os

bp = Blueprint("net_ingest", __name__)

@bp.route("/net/ingest", methods=["POST"])
def net_ingest():
    """Fetches URL and saves to inbox/ for later processing."""
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"ok": False, "error": "No URL"}), 400
        
    res = net_manager.ingest_url(url)
    
    if res["ok"]:
        # Save to Inbox (Earth principle: sterile wound)
        ts = int(time.time())
        fname = f"data/inbox/web_{ts}.txt"
        os.makedirs("data/inbox", exist_ok=True)
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\nTITLE: {res.get(\"title\")}\n\n{res[\"text\"]}")
        
        return jsonify({"ok": True, "file": fname, "title": res.get("title")})
    
    return jsonify(res)
'@

# --- EXECUTION ---

$ts = Get-Date -Format "yyyyMMdd_HHmmss"

$targets = @(
  @{ rel="modules\net_bridge.py";                 content=$code_net_bridge },
  @{ rel="modules\net_cache.py";                  content=$code_net_cache },
  @{ rel="modules\net_manager.py";                content=$code_net_manager },
  @{ rel="modules\html_extract.py";               content=$code_html_extract },
  @{ rel="modules\url_ingest.py";                 content=$code_url_ingest },
  @{ rel="routes\ester_net_fetch_routes.py";      content=$code_routes_fetch },
  @{ rel="routes\ester_net_ingest_url_routes.py"; content=$code_routes_ingest }
)

$backups = @()

try {
  Write-Host "Starting Ester Patch v1.1..."
  
  # 1. Backup Phase
  foreach ($t in $targets) {
    $p = Join-Path $ProjectRoot $t.rel
    $bak = Backup-File $p $ts
    if ($bak) { $backups += @{ path=$p; bak=$bak } }
  }

  # 2. Write Phase
  foreach ($t in $targets) {
    $p = Join-Path $ProjectRoot $t.rel
    if ($null -eq $t.content) { throw "Critical Logic Error: Content is null for $($t.rel)" }
    Write-Host "Writing: $($t.rel)"
    Write-FileUtf8NoBom $p $t.content
  }

  # 3. Compilation Check
  $py = Join-Path $ProjectRoot "venv\Scripts\python.exe"
  if (!(Test-Path $py)) { $py = "python" }

  Write-Host "Compiling modules to verify syntax..."
  foreach ($t in $targets) {
      $p = Join-Path $ProjectRoot $t.rel
      & $py -m py_compile $p
  }

  Write-Host "---------------------------------------------------"
  Write-Host "[SUCCESS] Patch v1.1 applied."
  Write-Host "Modules: Bridge (Pure), Cache (JSON), Manager (Orch), Extract (BS4)."
  Write-Host "Action: Restart app.py to activate new routes."
  Write-Host "---------------------------------------------------"

} catch {
  Write-Host "[ERR] Patch failed: $($_.Exception.Message)"
  Write-Host "Rolling back..."
  foreach ($b in $backups) {
    if ($b.bak -and (Test-Path $b.bak)) {
      Copy-Item -LiteralPath $b.bak -Destination $b.path -Force
    }
  }
  throw
}