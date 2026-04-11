# -*- coding: utf-8 -*-
"""patches/integrate_web_browser.py - patch dlya integratsii polnotsennogo web-brauzera v Ester.

PROBLEM:
Ester govorila "dostup v internet ogranichen" potomu chto mogla tolko ISKAT,
no ne ChITAT soderzhimoe naydennykh stranits.

RESOLUTION:
1. Addavit bridges/web_browser.py
2. Integrated ego v thinking pipeline
3. Add new nastroyki v.env

INSTRUKTsIYa PO PRIMENENIYu:

1. Skopirovat fayly:
   copy web_browser.py <repo-root>\bridges\web_browser.py

2.Adbavit v.env:
   WEB_BROWSER_ENABLED=1
   WEB_BROWSER_MODE=light
   WEB_BROWSER_TIMEOUT_SEC=15
   WEB_BROWSER_MAX_PAGES_PER_QUERY=5

3. (Optsionalno) Ustanovit zavisimosti dlya rezhimov medium/full:
   pip install requests-html # dlya medium
   pip install playwright && playwright install chromium # dlya full

4. Primenit patch k web_context_expander.py (sm. nizhe)

5. Perezapustit Ester

# c=a+b"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def patch_web_context_expander(project_root: str) -> dict:
    """Patch modules/thinking/web_context_expander.po to use web_browser.
    
    Returns a dictionary with the result."""
    result = {"ok": False, "message": "", "backup": None}
    
    target = Path(project_root) / "modules" / "thinking" / "web_context_expander.py"
    if not target.exists():
        result["message"] = f"File not found: {target}"
        return result
    
    # Bekap
    backup = target.with_suffix(".py.bak")
    content = target.read_text(encoding="utf-8")
    backup.write_text(content, encoding="utf-8")
    result["backup"] = str(backup)
    
    # Checking if the patch has already been applied
    if "from bridges.web_browser import" in content:
        result["message"] = "Patch already applied"
        result["ok"] = True
        return result
    
    # Patch 1: Add import web_browser
    import_patch = '''from typing import Any, Dict, List

# === PATCH: Import web_browser for full page reading ===
try:
    from bridges.web_browser import browse, search_and_read, WebPage
    WEB_BROWSER_AVAILABLE = True
except ImportError:
    WEB_BROWSER_AVAILABLE = False
    WebPage = None #type: ignore
# === END PATCH ===

WEB_CONTEXT_AB ='''
    
    content = re.sub(
        r"from typing import Any, Dict, List\s*\n\s*WEB_CONTEXT_AB =",
        import_patch,
        content,
        count=1
    )
    
    # Patch 2: Modify the expand() function to read pages
    expand_patch = '''def expand(q: str, k: int = 5, autofetch: bool = False, max_fetch: int = 3, read_content: bool = True) -> Dict[str, Any]:
    """
    Rasshiryaet kontekst cherez web-poisk.
    
    PATCH: Added parametr read_content dlya chteniya soderzhimogo stranits.
    """
    from modules.web_search import search_web # lokalnyy import dlya ustoychivosti
    _CNT["expand_calls"] += 1
    hits = search_web(q, topk=max(1, min(k, 10))) or []
    jobs: List[Dict[str, Any]] = []
    pages_content: List[Dict[str, Any]] = [] # PATCH: soderzhimoe stranits
    
    # PATCH: Chitaem soderzhimoe stranits cherez web_browser
    if read_content and WEB_BROWSER_AVAILABLE and hits:
        for hit in hits[:max_fetch]:
            url = hit.get("url")
            if not url:
                continue
            try:
                page = browse(url)
                if page.ok():
                    pages_content.append({
                        "url": url,
                        "title": page.title,
                        "text": page.text[:5000],  # Limit teksta
                        "meta": page.meta_description,
                    })
            except Exception as e:
                pages_content.append({"url": url, "error": str(e)})
    #END PATCH
    
    do_fetch = AUTO or bool(autofetch)
    if WEB_CONTEXT_AB == "B":
        do_fetch = False'''
    
    # Find the beginning of the expand function and replace
    content = re.sub(
        r"def expand\(q: str, k: int = 5, autofetch: bool = False, max_fetch: int = 3\) -> Dict\[str, Any\]:\s*\n.*?from modules\.web_search import search_web.*?\n.*?_CNT\[\"expand_calls\"\].*?\n.*?hits = search_web.*?\n.*?jobs:.*?\n.*?do_fetch = AUTO.*?\n.*?if WEB_CONTEXT_AB == \"B\":.*?\n.*?do_fetch = False",
        expand_patch,
        content,
        flags=re.DOTALL
    )
    
    # Patch 3: Add pages_content v return
    content = re.sub(
        r'return \{"ok": True, "q": q, "items": hits, "jobs": jobs, "autofetch": do_fetch\}',
        'return {"ok": True, "q": q, "items": hits, "jobs": jobs, "autofetch": do_fetch, "pages_content": pages_content}',
        content
    )
    
    # Zapisyvaem
    target.write_text(content, encoding="utf-8")
    
    result["ok"] = True
    result["message"] = f"Patched successfully. Backup: {backup}"
    return result


def add_env_settings(project_root: str) -> dict:
    """Adds web_browser settings to .env"""
    result = {"ok": False, "message": "", "added": []}
    
    env_file = Path(project_root) / ".env"
    if not env_file.exists():
        result["message"] = f".env not found: {env_file}"
        return result
    
    content = env_file.read_text(encoding="utf-8")
    
    # Settings to add
    new_settings = [
        "",
        "# === WEB BROWSER (full access to pages) ===",
        "WEB_BROWSER_ENABLED=1",
        "WEB_BROWSER_MODE=light",
        "WEB_BROWSER_TIMEOUT_SEC=15",
        "WEB_BROWSER_MAX_PAGES_PER_QUERY=5",
        "WEB_BROWSER_CACHE_TTL_SEC=600",
        "WEB_BROWSER_UA=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Ester/2.0",
        "# WEB_BROWSER_BLOCKED_DOMAINS=evil.com,spam.org",
    ]
    
    # Checking whether they have already been added
    if "WEB_BROWSER_ENABLED" in content:
        result["message"] = "Web browser settings already in .env"
        result["ok"] = True
        return result
    
    # Dobavlyaem
    content += "\n" + "\n".join(new_settings) + "\n"
    env_file.write_text(content, encoding="utf-8")
    
    result["ok"] = True
    result["message"] = f"Added {len(new_settings)-1} settings to .env"
    result["added"] = new_settings[2:-1]  # No empty lines or comments
    return result


def install_web_browser_module(project_root: str, source_file: str) -> dict:
    """
    Kopiruet web_browser.py v bridges/
    """
    result = {"ok": False, "message": ""}
    
    src = Path(source_file)
    if not src.exists():
        result["message"] = f"Source file not found: {src}"
        return result
    
    dest_dir = Path(project_root) / "bridges"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest = dest_dir / "web_browser.py"
    
    # Kopiruem
    content = src.read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    
    result["ok"] = True
    result["message"] = f"Installed: {dest}"
    return result


def main():
    """SLI to apply the patch."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python integrate_web_browser.py <project_root> [web_browser.py]")
        print("")
        print("Example:")
        print("  python integrate_web_browser.py <repo-root> web_browser.py")
        sys.exit(1)
    
    project_root = sys.argv[1]
    source_file = sys.argv[2] if len(sys.argv) > 2 else "web_browser.py"
    
    print(f"Project root: {project_root}")
    print(f"Source file: {source_file}")
    print("-" * 60)
    
    # 1. Ustanavlivaem modul
    print("\n1. Installing web_browser module...")
    r1 = install_web_browser_module(project_root, source_file)
    print(f"   {'✓' if r1['ok'] else '✗'} {r1['message']}")
    
    # 2. Patchim web_context_expander
    print("\n2. Patching web_context_expander.py...")
    r2 = patch_web_context_expander(project_root)
    print(f"   {'✓' if r2['ok'] else '✗'} {r2['message']}")
    if r2.get("backup"):
        print(f"   Backup: {r2['backup']}")
    
    # 3. Add settings
    print("\n3. Adding .env settings...")
    r3 = add_env_settings(project_root)
    print(f"   {'✓' if r3['ok'] else '✗'} {r3['message']}")
    if r3.get("added"):
        for s in r3["added"]:
            print(f"      {s}")
    
    # Itog
    print("\n" + "=" * 60)
    all_ok = r1["ok"] and r2["ok"] and r3["ok"]
    if all_ok:
        print("✓ Patch applied successfully!")
        print("")
        print("Next steps:")
        print("1. Restart Ester")
        print("2. Test: /web browse https://example.com")
        print("")
        print("Optional (for medium/full modes):")
        print("  pip install requests-html")
        print("  pip install playwright && playwright install chromium")
    else:
        print("✗ Patch failed. Check errors above.")
    
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

# c=a+b
