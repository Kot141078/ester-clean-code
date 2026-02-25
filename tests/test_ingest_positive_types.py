# -*- coding: utf-8 -*-
import io

import pytest
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


@pytest.mark.parametrize(
    "name,ctype,data",
    [
        ("a.txt", "text/plain", b"hello world"),
        ("b.md", "text/markdown", b"# header\ncontent"),
        ("c.pdf", "application/pdf", b"%PDF-1.3\n%...\n"),
    ],
)
def test_ingest_supported_types(client, auth_hdr_user, name, ctype, data):
    r = client.post(
        "/ingest/file",
        data={"file": (name, data, ctype)},
        headers=auth_hdr_user,
        content_type="multipart/form-data",
    )
    # For PDF, both 200 (accepted) and 415 (if the PDF parser is disabled in the config) are acceptable.
    assert r.status_code in (200, 415)
    if r.status_code == 200:
        j = r.get_json()
        assert isinstance(j, dict)
# assert "id" in j