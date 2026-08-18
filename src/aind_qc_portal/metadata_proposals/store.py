"""S3-backed storage for proposed DocDB metadata changes.

A *proposal* is one user's suggested replacement for a DocDB record. It is
written to S3 as soon as it is created, so it survives a QC-portal restart —
unlike the in-memory pending table this replaces — and stays around afterwards
as an audit trail of who proposed and who approved what.

Object layout (bucket ``aind-scratch-data``, prefix ``metadata-proposals/``)::

    metadata-proposals/{proposal_id}.json

One object per proposal, rewritten in place on every status transition. The
flat layout keeps ``get_proposal`` a single ``GetObject`` and the queue listing
one ``ListObjectsV2`` plus a parallel read of each object; the queue is small
(tens of open proposals) so this is cheaper than maintaining an index.

Envelope::

    {
      "proposal_id":  "<uuid4>",
      "version":      "v1" | "v2",          # which DocDB
      "record_id":    "<_id>",
      "record_name":  "<name>",             # denormalised for the queue table
      "body":         {...},                # full proposed record
      "body_hash":    "<sha256 of canonical body>",
      "base":         {...},                # live record when the proposal was made
      "base_hash":    "<sha256 of canonical base>",
      "note":         "<free text>",
      "author":       "<QC portal user>",
      "created_at":   "<ISO-8601 UTC>",
      "status":       "open" | "applied" | "rejected" | "withdrawn" | "superseded",
      "reviewer":     "<QC portal user>" | null,
      "reviewed_at":  "<ISO-8601 UTC>" | null,
      "reason":       "<rejection reason>" | null,
      "supersedes":   "<proposal_id>" | null,
      "superseded_by": "<proposal_id>" | null,
      "docdb_status": <int> | null,
      "docdb_response": <any> | null
    }

The ``base`` snapshot is what makes review meaningful: the reviewer sees
``base -> body`` (what the author intended) and the server re-checks
``base_hash`` against live DocDB at approve time, so a proposal can never
silently overwrite a record that moved underneath it.
"""

import hashlib
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

S3_BUCKET = os.environ.get("METADATA_PROPOSALS_BUCKET", "aind-scratch-data")
S3_PREFIX = os.environ.get("METADATA_PROPOSALS_PREFIX", "metadata-proposals").strip("/")

PROPOSAL_STATUSES = ("open", "applied", "rejected", "withdrawn", "superseded")

# Proposed bodies are public on purpose: anyone can inspect a change before it
# lands, so nothing in the envelope is redacted for unauthenticated callers.

_LIST_WORKERS = 8


def _s3():
    """Return a boto3 S3 client."""
    return boto3.client("s3")


def _key(proposal_id: str) -> str:
    """Return the S3 key holding *proposal_id*."""
    return f"{S3_PREFIX}/{proposal_id}.json"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(obj: Any) -> str:
    """Return the sha256 of *obj* serialised as canonical (key-sorted) JSON."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_proposal(
    *,
    version: str,
    record_id: str,
    record_name: Optional[str],
    body: dict,
    base: Optional[dict],
    note: str,
    author: str,
    supersedes: Optional[str] = None,
) -> dict:
    """Build (but do not store) a fresh proposal envelope."""
    return {
        "proposal_id": str(uuid.uuid4()),
        "version": version,
        "record_id": str(record_id),
        "record_name": record_name,
        "body": body,
        "body_hash": canonical_hash(body),
        "base": base,
        "base_hash": canonical_hash(base) if base is not None else None,
        "note": note or "",
        "author": author,
        "created_at": _now_iso(),
        "status": "open",
        "reviewer": None,
        "reviewed_at": None,
        "reason": None,
        "supersedes": supersedes,
        "superseded_by": None,
        "docdb_status": None,
        "docdb_response": None,
    }


def put_proposal(proposal: dict) -> None:
    """Write *proposal* to S3, overwriting any previous revision of it."""
    _s3().put_object(
        Bucket=S3_BUCKET,
        Key=_key(proposal["proposal_id"]),
        Body=json.dumps(proposal, default=str).encode(),
        ContentType="application/json",
    )


def get_proposal(proposal_id: str) -> Optional[dict]:
    """Return the proposal with *proposal_id*, or None if it does not exist."""
    try:
        response = _s3().get_object(Bucket=S3_BUCKET, Key=_key(proposal_id))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(response["Body"].read().decode())


def _list_keys() -> list:
    """Return every proposal object key under the store prefix."""
    paginator = _s3().get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                keys.append(obj["Key"])
    return keys


def _read_key(key: str) -> Optional[dict]:
    """Return the proposal stored at *key*, or None if it is missing or corrupt."""
    try:
        response = _s3().get_object(Bucket=S3_BUCKET, Key=key)
    except ClientError:
        return None
    try:
        return json.loads(response["Body"].read().decode())
    except (ValueError, UnicodeDecodeError):
        return None


def list_proposals(
    status: Optional[str] = None,
    version: Optional[str] = None,
    record_id: Optional[str] = None,
) -> list:
    """Return stored proposals, newest first, filtered by the given criteria.

    ``status`` may be a single status or a comma-separated list; ``None`` (or
    the literal ``"all"``) returns every status.
    """
    keys = _list_keys()
    if not keys:
        return []

    wanted = None
    if status and status != "all":
        wanted = {s.strip() for s in status.split(",") if s.strip()}

    with ThreadPoolExecutor(max_workers=_LIST_WORKERS) as pool:
        proposals = [p for p in pool.map(_read_key, keys) if p]

    def keep(p: dict) -> bool:
        """Return True if *p* satisfies every requested filter."""
        if wanted is not None and p.get("status") not in wanted:
            return False
        if version and p.get("version") != version:
            return False
        if record_id and str(p.get("record_id")) != str(record_id):
            return False
        return True

    matches = [p for p in proposals if keep(p)]
    matches.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return matches
