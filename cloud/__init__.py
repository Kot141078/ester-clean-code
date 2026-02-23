# -*- coding: utf-8 -*-
"""
S3/MinIO adapter dlya bekapov.
Trebuetsya: boto3
Konfiguratsiya cherez ENV:
  BACKUP_S3_ENDPOINT, BACKUP_S3_REGION, BACKUP_S3_BUCKET,
  BACKUP_S3_ACCESS_KEY, BACKUP_S3_SECRET_KEY, BACKUP_S3_PATH_STYLE=1/0
"""
from __future__ import annotations

import os
import pathlib
from typing import List

try:
    import boto3  # type: ignore
    from botocore.config import Config  # type: ignore
except Exception:
    boto3 = None  # type: ignore
    Config = None  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _client():
    if boto3 is None or Config is None:
        raise RuntimeError("cloud adapter requires boto3; install optional dependency")
    endpoint = os.getenv("BACKUP_S3_ENDPOINT", "http://localhost:9000")
    region = os.getenv("BACKUP_S3_REGION", "us-east-1")
    key = os.getenv("BACKUP_S3_ACCESS_KEY", "minioadmin")
    secret = os.getenv("BACKUP_S3_SECRET_KEY", "minioadmin")
    path_style = os.getenv("BACKUP_S3_PATH_STYLE", "1") == "1"
    cfg = Config(s3={"addressing_style": "path" if path_style else "virtual"})
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=region,
        config=cfg,
    )


def _bucket() -> str:
    b = os.getenv("BACKUP_S3_BUCKET", "ester-backups")
    return b


def upload_file(local_path: str, remote_key: str) -> str:
    cli = _client()
    bucket = _bucket()
    cli.upload_file(local_path, bucket, remote_key)
    return f"s3://{bucket}/{remote_key}"


def download_file(remote_key: str, local_path: str) -> str:
    cli = _client()
    bucket = _bucket()
    pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    cli.download_file(bucket, remote_key, local_path)
    return local_path


def list_keys(prefix: str = "") -> List[str]:
    cli = _client()
    bucket = _bucket()
    keys: List[str] = []
    token = None
    while True:
        kw = dict(Bucket=bucket, Prefix=prefix)
        if token:
            kw["ContinuationToken"] = token
        resp = cli.list_objects_v2(**kw)
        for it in resp.get("Contents", []) or []:
            keys.append(it["Key"])
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return keys
