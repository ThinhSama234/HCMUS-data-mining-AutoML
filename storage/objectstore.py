"""Object storage (FR-013) — MinIO/S3 when `S3_ENDPOINT` is set, else a local-dir fallback.

The database stores only a URI (`s3://bucket/key` or `file://…`); bytes live here. The local
fallback means upload/ingest works with no MinIO running (dev/tests).
"""
from __future__ import annotations

import os

from storage.db import REPO_ROOT

BUCKETS = ("datasets", "predictions", "models", "figures")
_LOCAL_ROOT = os.path.join(REPO_ROOT, ".objectstore")


def _enabled():
    return bool(os.environ.get("S3_ENDPOINT"))


def _client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "amlb"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "amlb12345"),
        region_name="us-east-1",
    )


def ensure_buckets():
    if not _enabled():
        for b in BUCKETS:
            os.makedirs(os.path.join(_LOCAL_ROOT, b), exist_ok=True)
        return
    c = _client()
    existing = {b["Name"] for b in c.list_buckets().get("Buckets", [])}
    for b in BUCKETS:
        if b not in existing:
            c.create_bucket(Bucket=b)


def put(bucket, key, data: bytes) -> str:
    """Store bytes under bucket/key; return the URI to persist in the DB."""
    ensure_buckets()
    if _enabled():
        _client().put_object(Bucket=bucket, Key=key, Body=data)
        return f"s3://{bucket}/{key}"
    path = os.path.join(_LOCAL_ROOT, bucket, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return f"file://{path}"


def get(uri: str) -> bytes:
    if uri.startswith("file://"):
        with open(uri[len("file://"):], "rb") as f:
            return f.read()
    # s3://bucket/key
    _, _, rest = uri.partition("s3://")
    bucket, _, key = rest.partition("/")
    return _client().get_object(Bucket=bucket, Key=key)["Body"].read()


def presign(uri: str, expires=3600) -> str:
    if uri.startswith("file://") or not _enabled():
        return uri
    _, _, rest = uri.partition("s3://")
    bucket, _, key = rest.partition("/")
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)
