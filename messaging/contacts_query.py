# -*- coding: utf-8 -*-
"""
messaging/contacts_query.py — servernye filtry i paginatsiya spiska kontaktov.

MOSTY:
- (Yavnyy) list_contacts_paged_filtered(limit, offset, channel, contains) → (key, agree, rate, persona, last_ts, silence_until).
- (Skrytyy #1) Kanal filtruetsya po prefiksu klyucha 'telegram:'/'whatsapp:' — sovmestimo s tekuschim formatom klyuchey.
- (Skrytyy #2) Nikakikh izmeneniy skhemy — ispolzuem tot zhe UNION i JOIN, chto i bazovaya vydacha.

ZEMNOY ABZATs:
Sotni i tysyachi kontaktov teper listayutsya i filtruyutsya na servere — bystree, chem pytatsya iskat glazami v ogromnoy tablitse.

# c=a+b
"""
from __future__ import annotations

from typing import List, Tuple, Optional

from messaging.optin_store import _conn  # ispolzuem suschestvuyuschee podklyuchenie/DDL
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def list_contacts_paged_filtered(
    limit: int = 50,
    offset: int = 0,
    channel: Optional[str] = None,   # "telegram" | "whatsapp" | None
    contains: str = ""               # podstroka v key
) -> List[Tuple[str, bool, int, str, float, float]]:
    ch_prefix = None
    if channel in ("telegram", "whatsapp"):
        ch_prefix = f"{channel}:"

    like = f"%{contains}%" if contains else None

    q = """
    WITH keys AS (
        SELECT key FROM optin
        UNION SELECT key FROM prefs
        UNION SELECT key FROM outbound
        UNION SELECT key FROM silence
    )
    SELECT k.key,
           COALESCE(o.agree,0) AS agree,
           COALESCE(p.rate_per_h,6) AS rate_per_h,
           COALESCE(p.persona,'gentle') AS persona,
           COALESCE(b.last_ts,0) AS last_ts,
           COALESCE(s.until_ts,0) AS silence_until
    FROM keys k
    LEFT JOIN optin o    ON o.key=k.key
    LEFT JOIN prefs p    ON p.key=k.key
    LEFT JOIN outbound b ON b.key=k.key
    LEFT JOIN silence s  ON s.key=k.key
    WHERE 1=1
      {ch_filter}
      {contains_filter}
    ORDER BY COALESCE(b.last_ts,0) DESC, k.key
    LIMIT ? OFFSET ?
    """

    ch_clause = "AND k.key LIKE ? || '%'" if ch_prefix else ""
    con_clause = "AND k.key LIKE ?" if like else ""

    params = []
    if ch_prefix: params.append(ch_prefix)
    if like: params.append(like)
    params.extend([int(limit), int(offset)])

    q = q.format(ch_filter=ch_clause, contains_filter=con_clause)

    with _conn() as c:
        rows = c.execute(q, tuple(params)).fetchall()
        return [(str(r[0]), bool(int(r[1])), int(r[2]), str(r[3]), float(r[4]), float(r[5])) for r in rows]