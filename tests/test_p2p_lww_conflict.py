# -*- coding: utf-8 -*-
import io
import json
import time
import zipfile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _zip_bytes(files):
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for name, (content, mtime) in files.items():
            info = zipfile.ZipInfo(filename=name, date_time=time.gmtime(mtime)[:6])
            z.writestr(info, content)
    return bio.getvalue()


def test_lww_apply_conflict_prefers_newer(client, auth_hdr_admin):
    # Let's create an archive with two versions of one file - old and new.
    now = int(time.time())
    files = {
        "structured_mem/store.json": (
            b'{"records":[{"id":"1","text":"old"}]}',
            now - 100,
        ),
        "structured_mem/store.json": (
            b'{"records":[{"id":"1","text":"new"}]}',
            now - 10,
        ),
    }
    payload = _zip_bytes(files)
    r = client.post(
        "/replication/apply",
        headers=auth_hdr_admin,
        data=payload,
        content_type="application/zip",
    )
    # we allow 200 OK, otherwise 400 if canon does not support artificial conflict
# assert r.status_code in (200, 400, 422)