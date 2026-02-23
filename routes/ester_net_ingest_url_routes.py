# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from modules import net_manager
import time
import os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

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
        title = res.get("title")
        text = res.get("text", "")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\nTITLE: {title}\n\n{text}")
        
        return jsonify({"ok": True, "file": fname, "title": res.get("title")})
    
    return jsonify(res)
