
# -*- coding: utf-8 -*-
"""
Google Drive adapter dlya bekapov (Service Account).
Trebuetsya: google-api-python-client, google-auth
ENV:
  GDRIVE_SERVICE_ACCOUNT_FILE=./secrets/gdrive_sa.json
  GDRIVE_BACKUP_FOLDER_ID=<folder_id>
"""
from __future__ import annotations

import io
import os
import pathlib
from typing import List, Tuple

from google.oauth2 import service_account  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.http import MediaFileUpload  # type: ignore
from googleapiclient.http import MediaIoBaseDownload
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

SCOPES = ['https://www.googleapis.com/auth/drive']

def _service():
    sa_path = os.getenv('GDRIVE_SERVICE_ACCOUNT_FILE', './secrets/gdrive_sa.json')
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

def upload_file(local_path: str, file_name: str = None, folder_id: str = None) -> str:
    svc = _service()
    folder_id = folder_id or os.getenv('GDRIVE_BACKUP_FOLDER_ID', 'root')
    file_name = file_name or os.path.basename(local_path)
    media = MediaFileUpload(local_path, resumable=True)
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    f = svc.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
    return f['id']

def list_files(prefix: str = '', folder_id: str = None) -> List[Tuple[str, str]]:
    svc = _service()
    folder_id = folder_id or os.getenv('GDRIVE_BACKUP_FOLDER_ID', 'root')
    q = f"'{folder_id}' in parents and trashed=false"
    if prefix:
        q += f" and name contains '{prefix.replace("'", "\'")}'"
    items = []
    page_token = None
    while True:
        resp = svc.files().list(q=q, fields="nextPageToken, files(id, name)", pageToken=page_token).execute()
        for f in resp.get('files', []):
            items.append((f['id'], f['name']))
        page_token = resp.get('nextPageToken', None)
        if not page_token:
            break
    return items

def download_file(file_id: str, local_path: str) -> str:
    svc = _service()
    req = svc.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, 'wb') as out:
        out.write(fh.getvalue())
# return local_path  # Fixed: unterminated string literal (detected at line 43) (<unknown>, line 43)