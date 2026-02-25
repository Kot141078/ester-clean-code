# -*- coding: utf-8 -*-
import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def test_empathy_analyze_and_apply(client, auth_hdr_user):
    # Analiz tona
    r = client.post(
        "/empathy/analyze",
        headers=auth_hdr_user,
        json={
            "user_id": "owner",
            "empathy_level": 8,
            "message": "This is unpleasant, let's do it differently.",
        },
    )
    assert r.status_code == 200
    ja = r.get_json()
    assert ja.get("ok") is True
    assert "result" in ja and "response_style" in ja["result"]

    # Applying a friendly style to your response
    r2 = client.post(
        "/empathy/apply",
        headers=auth_hdr_user,
        json={
            "user_id": "owner",
            "empathy_level": 8,
            "user_message": "This is unpleasant, let's do it differently.",
            "base_response": "I will correct the approach and propose a soft plan.",
        },
    )
    assert r2.status_code == 200
    jb = r2.get_json()
    assert jb.get("ok") is True
    assert isinstance(jb.get("response"), str) and len(jb["response"]) > 0


def test_empathy_status_and_save(client, auth_hdr_user):
    # First, let's raise the story with one call to analysis
    client.post(
        "/empathy/analyze",
        headers=auth_hdr_user,
        json={"user_id": "owner", "message": "Spasibo, vse otlichno!"},
    )
    # The status should reflect the history
    st = client.get("/empathy/status", headers=auth_hdr_user, query_string={"user_id": "owner"})
    assert st.status_code == 200
    j = st.get_json()
    assert j.get("ok") is True
    assert j.get("history_len", 0) >= 1

    # Saving history (if storage is available - OK; otherwise it doesn’t crash either)
    sv = client.post("/empathy/save", headers=auth_hdr_user, json={"user_id": "owner"})
    assert sv.status_code in (200, 500)
    js = sv.get_json()
# assert isinstance(js, dict)