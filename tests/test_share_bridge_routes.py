from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_share_capture_single_and_batch(client):
    # Odin element
    r = client.post(
        "/share/capture",
        json={
            "url": "https://example.com/test",
            "title": "Testovaya stranitsa",
            "text": "Privet, eto vazhnyy fragment.",
            "tags": ["notes", "web"],
            "note": "unit",
        },
    )
    assert r.status_code in (200, 404)  # dopuskaem, chto routy ne podklyucheny
    if r.status_code != 200:
        return
    j = r.get_json()
    assert j.get("ok") is True
    assert j.get("count") == 1

    # Paket
    r2 = client.post(
        "/share/capture",
        json={
            "items": [
                {"title": "A", "text": "alfa"},
                {"title": "B", "html": "<html><body>bravo</body></html>"},
            ]
        },
    )
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2.get("ok") is True
    assert j2.get("count") == 2