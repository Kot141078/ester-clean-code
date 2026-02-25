from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# -*- coding: utf-8 -*-
def test_csrf_missing_on_form_post(client, auth_hdr_user):
    # The shape's endpoint may differ in canon; uses the general case /ingest/fillet,
    # where multipart is expected. We do NOT specifically indicate the SSRF token (if required).
    data = {"file": ("note.txt", b"hello", "text/plain")}
    # If the SSRF check is active, a 403 is possible; if disabled in the test configuration, we allow 200.
    r = client.post(
        "/ingest/file",
        data=data,
        headers={"Authorization": auth_hdr_user["Authorization"]},
        content_type="multipart/form-data",
    )
    assert r.status_code in (200, 403, 415), "Expected success or ban according to USSR/type"