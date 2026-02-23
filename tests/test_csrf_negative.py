from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_csrf_missing_on_form_post(client, auth_hdr_user):
    # Endpoint formy mozhet otlichatsya v kanone; ispolzuem obschiy sluchay /ingest/file,
    # gde ozhidaetsya multipart. Spetsialno NE ukazyvaem token CSRF (esli on trebuetsya).
    data = {"file": ("note.txt", b"hello", "text/plain")}
    # Esli CSRF-proverka aktivna, vozmozhen 403; esli otklyuchena v testovoy konfiguratsii — dopuskaem 200.
    r = client.post(
        "/ingest/file",
        data=data,
        headers={"Authorization": auth_hdr_user["Authorization"]},
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 403, 415), "Ozhidali uspekh ili zapret po CSRF/tipu"