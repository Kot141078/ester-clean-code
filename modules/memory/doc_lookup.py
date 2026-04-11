from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from modules.memory import doc_store
from modules.memory import recent_docs


_DOC_ID_RE = re.compile(r"\b[a-f0-9]{64}\b", re.IGNORECASE)
_QUOTED_FILE_RE = re.compile(r"[\"'«»“”](.{1,120}?\.(?:txt|md|pdf|docx?|html?))[\"'«»“”]", re.IGNORECASE)
_FILE_RE = re.compile(
    r"(?iu)([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9 _().,\-]{0,120}\.(?:txt|md|pdf|docx?|html?))"
)

_LEADING_NAME_PREFIXES = (
    "в файле ",
    "во файле ",
    "из файла ",
    "файл ",
    "файле ",
    "документ ",
    "документе ",
    "из документа ",
    "про файл ",
    "про документ ",
    "file ",
    "document ",
    "doc ",
)
_LEADING_NAME_TOKENS = {
    "в",
    "во",
    "из",
    "про",
    "по",
    "о",
    "об",
    "файл",
    "файле",
    "документ",
    "документе",
    "file",
    "document",
    "doc",
}

_STRICT_DOC_MARKERS = (
    "файл",
    "документ",
    "pdf",
    "txt",
    "md",
    "summary",
    "резюме",
    "конспект",
    "вывод",
    "итог",
    "страниц",
    "страницы",
    "страница",
    "цитат",
    "цитаты",
    "цитата",
)

_FOLLOWUP_MARKERS = (
    "этот пост",
    "этот файл",
    "этот документ",
    "это все",
    "это всё",
    "и это все",
    "и это всё",
    "об этом",
    "по нему",
    "по ней",
    "там",
    "что скажешь",
    "что думаешь",
    "прочитал",
    "прочитала",
    "прочитан",
    "прочитанном",
    "больше ничего",
    "и больше ничего",
)

_SEMANTIC_DOC_MARKERS = (
    "документ",
    "документы",
    "файл",
    "протокол",
    "отчет",
    "отчёт",
    "спека",
    "спецификация",
    "мануал",
    "руководство",
    "пдф",
    "pdf",
    "readme",
    "report",
    "spec",
    "manual",
    "guide",
    "protocol",
)

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+", re.UNICODE)
_STOP_TOKENS = {
    "a",
    "an",
    "and",
    "doc",
    "document",
    "file",
    "html",
    "md",
    "of",
    "pdf",
    "summary",
    "txt",
    "в",
    "во",
    "все",
    "всё",
    "документ",
    "документе",
    "документы",
    "его",
    "ее",
    "её",
    "из",
    "итог",
    "как",
    "какой",
    "можешь",
    "нем",
    "нём",
    "о",
    "об",
    "по",
    "под",
    "пост",
    "посты",
    "про",
    "прочитала",
    "прочитал",
    "разве",
    "резюме",
    "скажи",
    "скажешь",
    "там",
    "текст",
    "ты",
    "увидела",
    "увидел",
    "файл",
    "файле",
    "что",
    "это",
    "этот",
}


def _normalize_text(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or ""))
    return " ".join(s.split()).strip().casefold()


def _normalize_name(name: str) -> str:
    return doc_store._normalize_doc_name(name)  # type: ignore[attr-defined]


def _clean_filename_candidate(raw: str) -> str:
    s = str(raw or "").strip()
    s = s.strip(" \t\r\n\"'`“”«»[](){}<>.,!?;:")
    parts = [part.strip(" \t\r\n\"'`“”«»[](){}<>.,!?;:") for part in s.split() if part.strip()]
    end = -1
    for idx in range(len(parts) - 1, -1, -1):
        if re.search(r"\.(?:txt|md|pdf|docx?|html?)$", parts[idx], re.IGNORECASE):
            end = idx
            break
    if end >= 0:
        picked = [parts[end]]
        for idx in range(end - 1, max(-1, end - 4), -1):
            token = parts[idx].strip()
            low = _normalize_text(token)
            if not token or low in _LEADING_NAME_TOKENS:
                break
            if not re.search(r"[A-Za-zА-Яа-я0-9]", token):
                break
            picked.insert(0, token)
        s = " ".join(picked)
    low = _normalize_text(s)
    changed = True
    while changed and low:
        changed = False
        for prefix in _LEADING_NAME_PREFIXES:
            if low.startswith(prefix):
                s = s[len(prefix) :].strip()
                low = _normalize_text(s)
                changed = True
                break
    return s.strip(" \t\r\n\"'`“”«»[](){}<>.,!?;:")


def extract_doc_id(query: str) -> str:
    m = _DOC_ID_RE.search(str(query or ""))
    if not m:
        return ""
    return m.group(0).strip().lower()


def extract_filename_candidates(query: str) -> List[str]:
    text = str(query or "")
    found: List[str] = []
    seen = set()

    def _push(value: str) -> None:
        cand = _clean_filename_candidate(value)
        if not cand:
            return
        key = _normalize_name(cand)
        if not key or key in seen:
            return
        seen.add(key)
        found.append(cand)

    for m in _QUOTED_FILE_RE.finditer(text):
        _push(m.group(1))
    for m in _FILE_RE.finditer(text):
        _push(m.group(1))
    return found


def is_recent_doc_followup_query(query: str) -> bool:
    low = _normalize_text(query)
    if not low:
        return False
    return any(marker in low for marker in _STRICT_DOC_MARKERS + _FOLLOWUP_MARKERS)


def _query_tokens(query: str, *, exclude_names: Optional[List[str]] = None) -> List[str]:
    low = _normalize_text(query)
    for name in exclude_names or []:
        if not name:
            continue
        low = low.replace(_normalize_text(name), " ")

    out: List[str] = []
    seen = set()
    for tok in _TOKEN_RE.findall(low):
        t = tok.casefold()
        if len(t) <= 2 or t in _STOP_TOKENS:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _is_semantic_doc_query(query: str, explicit_names: List[str]) -> bool:
    if explicit_names:
        return False
    low = _normalize_text(query)
    if not low:
        return False
    if any(marker in low for marker in _SEMANTIC_DOC_MARKERS):
        return True
    tokens = _query_tokens(query)
    return len(tokens) >= 4 and any(tok in low for tok in ("protocol", "guide", "report", "документ", "протокол"))


def _merge_doc_meta(base: Optional[Dict[str, Any]], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base or {})
    for key in ("doc_id", "name", "source_path", "summary", "citations", "created_at", "title", "passport_path"):
        val = overlay.get(key)
        if val not in (None, "", []):
            merged[key] = val
    if not merged.get("name") and overlay.get("orig_name"):
        merged["name"] = overlay.get("orig_name")
    return merged


def _meta_nested(meta: Dict[str, Any]) -> Dict[str, Any]:
    nested = meta.get("meta") if isinstance(meta.get("meta"), dict) else {}
    return dict(nested)


def _meta_title(meta: Dict[str, Any]) -> str:
    nested = _meta_nested(meta)
    return str(meta.get("title") or nested.get("title") or "").strip()


def _meta_passport_path(meta: Dict[str, Any]) -> str:
    nested = _meta_nested(meta)
    return str(meta.get("passport_path") or nested.get("passport_path") or "").strip()


def _meta_name(meta: Dict[str, Any]) -> str:
    return str(meta.get("name") or meta.get("orig_name") or "").strip()


def _same_chat(meta: Dict[str, Any], chat_id: Optional[int], user_id: Optional[int]) -> bool:
    if chat_id is None:
        return False
    nested = _meta_nested(meta)
    rec_chat = str(meta.get("chat_id") or nested.get("chat_id") or "").strip()
    rec_user = str(meta.get("user_id") or nested.get("user_id") or "").strip()
    if rec_chat != str(chat_id):
        return False
    if user_id is not None and rec_user and rec_user != str(user_id):
        return False
    return True


def _remember_resolution(
    meta: Dict[str, Any],
    *,
    chat_id: Optional[int],
    user_id: Optional[int],
    reason: str,
    uncertainty: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    out = dict(meta or {})
    out["_doc_resolve_reason"] = str(reason or "").strip()
    if uncertainty:
        out["_doc_recall_uncertainty"] = [dict(item) for item in uncertainty if isinstance(item, dict)]
    else:
        out.pop("_doc_recall_uncertainty", None)

    doc_id = str(out.get("doc_id") or "").strip()
    if chat_id is not None and doc_id:
        try:
            recent_docs.remember_last_resolved_document(
                chat_id,
                user_id,
                doc_id=doc_id,
                orig_name=_meta_name(out),
                title=_meta_title(out),
                source_path=str(out.get("source_path") or "").strip(),
                passport_path=_meta_passport_path(out),
                reason=str(reason or "").strip(),
            )
        except Exception:
            pass
    return out


def _resolve_bound_doc(chat_id: Optional[int], user_id: Optional[int], query: str) -> Optional[Dict[str, Any]]:
    if chat_id is None or not is_recent_doc_followup_query(query):
        return None
    binding = recent_docs.get_last_resolved_document(chat_id, user_id)
    doc_id = str(binding.get("doc_id") or "").strip()
    if not doc_id:
        return None
    meta = doc_store.get_doc_meta(doc_id)
    if not meta:
        return None
    recent_hit = recent_docs.find_recent_doc_entry(chat_id, doc_id)
    overlay = {
        "name": binding.get("orig_name") or binding.get("title") or "",
        "source_path": binding.get("source_path") or "",
        "passport_path": binding.get("passport_path") or "",
        "title": binding.get("title") or "",
    }
    merged = _merge_doc_meta(meta, overlay)
    if recent_hit:
        merged = _merge_doc_meta(merged, recent_hit)
    return merged


def _resolve_recent_doc(chat_id: Optional[int], query: str, explicit_names: List[str]) -> Optional[Dict[str, Any]]:
    if chat_id is None:
        return None
    entries = recent_docs.list_recent_docs(chat_id)
    if not entries:
        return None

    for name in explicit_names:
        target = _normalize_name(name)
        for rec in entries:
            rec_name = _normalize_name(str(rec.get("name") or rec.get("source_path") or ""))
            if rec_name and rec_name == target:
                meta = doc_store.get_doc_meta(str(rec.get("doc_id") or "")) if rec.get("doc_id") else None
                return _merge_doc_meta(meta, rec)

    if not is_recent_doc_followup_query(query):
        return None

    tokens = _query_tokens(query, exclude_names=explicit_names)
    best: Optional[Dict[str, Any]] = None
    best_score = -1
    for idx, rec in enumerate(entries):
        hay = _normalize_text(f"{rec.get('name') or ''}\n{rec.get('summary') or ''}")
        score = max(0, 100 - idx)
        if tokens:
            score += sum(6 for tok in tokens if tok in _normalize_text(str(rec.get("name") or "")))
            score += sum(2 for tok in tokens if tok in hay)
        if score > best_score:
            best_score = score
            best = rec
    if not isinstance(best, dict):
        return None
    meta = doc_store.get_doc_meta(str(best.get("doc_id") or "")) if best.get("doc_id") else None
    return _merge_doc_meta(meta, best)


def _semantic_uncertainty_candidates(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(hits) < 2:
        return []
    try:
        lead_score = float(hits[0].get("_semantic_score") or 0.0)
    except Exception:
        lead_score = 0.0
    if lead_score <= 0.0:
        return []

    out: List[Dict[str, Any]] = []
    for item in hits[1:4]:
        try:
            score = float(item.get("_semantic_score") or 0.0)
        except Exception:
            score = 0.0
        if score < max(6.0, lead_score - 16.0):
            continue
        out.append(
            {
                "name": _meta_name(item),
                "title": _meta_title(item),
                "source_path": str(item.get("source_path") or "").strip(),
                "score": score,
            }
        )
    return out


def resolve_doc_for_query(
    query: str,
    *,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    doc_id = extract_doc_id(query)
    if doc_id:
        meta = doc_store.get_doc_meta(doc_id)
        if meta:
            return _remember_resolution(meta, chat_id=chat_id, user_id=user_id, reason="doc_id")

    names = extract_filename_candidates(query)
    for name in names:
        matches = doc_store.find_docs_by_name(name, limit=3, chat_id=chat_id, user_id=user_id)
        if matches:
            return _remember_resolution(matches[0], chat_id=chat_id, user_id=user_id, reason="explicit_filename")

    for name in names:
        matches = doc_store.find_docs_by_name(name, limit=3)
        if matches:
            reason = "explicit_filename_global"
            if chat_id is not None and _same_chat(matches[0], chat_id, user_id):
                reason = "explicit_filename"
            return _remember_resolution(matches[0], chat_id=chat_id, user_id=user_id, reason=reason)

    if _is_semantic_doc_query(query, names):
        if chat_id is not None:
            semantic_same_chat = doc_store.search_docs(query, limit=4, chat_id=chat_id, user_id=user_id)
            if semantic_same_chat:
                uncertainty = _semantic_uncertainty_candidates(semantic_same_chat)
                return _remember_resolution(
                    semantic_same_chat[0],
                    chat_id=chat_id,
                    user_id=user_id,
                    reason="semantic_same_chat",
                    uncertainty=uncertainty,
                )
        semantic_global = doc_store.search_docs(query, limit=4)
        if semantic_global:
            uncertainty = _semantic_uncertainty_candidates(semantic_global)
            return _remember_resolution(
                semantic_global[0],
                chat_id=chat_id,
                user_id=user_id,
                reason="semantic_global",
                uncertainty=uncertainty,
            )

    bound_hit = _resolve_bound_doc(chat_id, user_id, query)
    if bound_hit:
        reason = str(recent_docs.get_last_resolved_document(chat_id, user_id).get("reason") or "").strip() or "recent_bound"
        return _remember_resolution(bound_hit, chat_id=chat_id, user_id=user_id, reason=reason)

    recent_hit = _resolve_recent_doc(chat_id, query, names)
    if recent_hit:
        reason = "recent_followup" if is_recent_doc_followup_query(query) else "recent_explicit"
        return _remember_resolution(recent_hit, chat_id=chat_id, user_id=user_id, reason=reason)
    return None


def _rank_chunks(chunks: List[Dict[str, Any]], query: str, explicit_names: List[str], top_k: int) -> List[Dict[str, Any]]:
    if not chunks:
        return []
    tokens = _query_tokens(query, exclude_names=explicit_names)
    scored = []
    for idx, chunk in enumerate(chunks):
        text = str(chunk.get("text") or "")
        hay = _normalize_text(text)
        score = 0
        if tokens:
            score += sum(10 for tok in tokens if tok in hay)
            score += max(0, 3 - idx)
        else:
            score = max(0, 10 - idx)
        scored.append((score, idx, chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    out = [chunk for _, _, chunk in scored[: max(1, int(top_k))]]
    out.sort(key=lambda item: int(item.get("_idx") or 0))
    return out


def _parse_page(citation: str) -> Optional[int]:
    m = re.search(r"\bp\.\s*(\d+)\b", str(citation or ""))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _trim_block(text: str, max_chars: int) -> str:
    s = str(text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _uncertainty_label(item: Dict[str, Any]) -> str:
    name = str(item.get("name") or item.get("title") or "").strip()
    source_path = str(item.get("source_path") or "").strip()
    source_name = os.path.basename(source_path) if source_path else ""
    if name and source_name and _normalize_name(name) != _normalize_name(source_name):
        return f"{name} ({source_name})"
    return name or source_name or "document"


def build_doc_context(doc_meta: Dict[str, Any], query: str) -> Dict[str, Any]:
    doc_id = str(doc_meta.get("doc_id") or "").strip()
    name = _meta_name(doc_meta) or os.path.basename(str(doc_meta.get("source_path") or "").strip()) or "document"
    title = _meta_title(doc_meta)
    source_path = str(doc_meta.get("source_path") or "").strip()
    summary = doc_store.load_summary(doc_id) if doc_id else ""
    if not summary:
        summary = str(doc_meta.get("summary") or "").strip()
    citations = doc_store.get_citations(doc_id) if doc_id else []
    if not citations:
        citations = [str(c or "").strip() for c in (doc_meta.get("citations") or []) if str(c or "").strip()]
    chunks = doc_store.load_chunks(doc_id) if doc_id else []
    for idx, chunk in enumerate(chunks):
        chunk["_idx"] = idx

    explicit_names = extract_filename_candidates(query)
    top_chunks = _rank_chunks(chunks, query, explicit_names, top_k=4)
    uncertainty = list(doc_meta.get("_doc_recall_uncertainty") or [])

    parts = ["[DOC_RESOLVED]", f"Файл: {name}"]
    if title and _normalize_text(title) != _normalize_text(name):
        parts.append(f"Заголовок: {title}")
    if doc_id:
        parts.append(f"doc_id: {doc_id}")
    if uncertainty:
        parts.append("[DOC_RECALL_UNCERTAINTY]")
        parts.append(
            "Скорее всего речь об этом документе, но рядом есть близкие совпадения. "
            "Если нужен другой документ, лучше уточнить имя файла или опорные детали."
        )
        for item in uncertainty[:3]:
            parts.append(f"- {_uncertainty_label(item)}")
    if summary:
        parts.append("[SUMMARY]")
        parts.append(_trim_block(summary, 2600))
    if top_chunks:
        parts.append("[MATCHED_CHUNKS]")
        for chunk in top_chunks:
            text = _trim_block(str(chunk.get("text") or ""), 900)
            cite = str(chunk.get("citation") or "").strip()
            if cite:
                parts.append(f"- {text}\n  {cite}")
            else:
                parts.append(f"- {text}")
    elif citations:
        parts.append("[CITATIONS]")
        parts.extend(f"- {cite}" for cite in citations[:12])

    provenance = []
    if doc_id or source_path:
        provenance.append(
            {
                "doc_id": doc_id,
                "path": source_path,
                "page": None,
                "offset": None,
            }
        )
    for chunk in top_chunks:
        citation = str(chunk.get("citation") or "").strip()
        provenance.append(
            {
                "doc_id": doc_id,
                "path": source_path,
                "page": _parse_page(citation),
                "offset": chunk.get("chunk_id"),
            }
        )

    return {
        "context": "\n".join([part for part in parts if str(part or "").strip()]).strip(),
        "provenance": provenance,
        "doc_id": doc_id,
        "source_path": source_path,
        "reason": str(doc_meta.get("_doc_resolve_reason") or "").strip(),
        "uncertainty": uncertainty,
    }


__all__ = [
    "build_doc_context",
    "extract_doc_id",
    "extract_filename_candidates",
    "is_recent_doc_followup_query",
    "resolve_doc_for_query",
]
