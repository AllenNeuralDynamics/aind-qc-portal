"""Storage for proposed DocDB metadata changes.

A *proposal* is one user's suggested replacement for a DocDB record. It is
stored as soon as it is created and records who proposed and who approved what.
The temporary in-memory backend is the default while the portal's S3
permissions are being repaired; set ``METADATA_PROPOSALS_BACKEND=s3`` to use
the durable S3 backend below.

The S3 object layout (bucket ``aind-scratch-data``, prefix
``metadata-proposals/``) is::

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
      "change_key":   "<opaque grouping hash>",
      "changed_sections": ["subject"],
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
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

S3_BUCKET = os.environ.get("METADATA_PROPOSALS_BUCKET", "aind-scratch-data")
S3_PREFIX = os.environ.get("METADATA_PROPOSALS_PREFIX", "metadata-proposals").strip("/")
METADATA_PROPOSALS_BACKEND = os.environ.get("METADATA_PROPOSALS_BACKEND", "memory").strip().lower()

PROPOSAL_STATUSES = ("open", "applied", "rejected", "withdrawn", "superseded")

# Proposed bodies are public on purpose: anyone can inspect a change before it
# lands, so nothing in the envelope is redacted for unauthenticated callers.

_LIST_WORKERS = 8
_MEMORY_PROPOSALS = {}
_MEMORY_LOCK = threading.RLock()
_MISSING = object()

_SUMMARY_FIELDS = (
    "proposal_id",
    "version",
    "record_id",
    "record_name",
    "body_hash",
    "base_hash",
    "note",
    "author",
    "created_at",
    "status",
    "reviewer",
    "reviewed_at",
    "reason",
    "supersedes",
    "superseded_by",
    "docdb_status",
)


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


def _json_equal(left: Any, right: Any) -> bool:
    """Return JavaScript-style structural equality for JSON-compatible values."""
    if left is _MISSING or right is _MISSING:
        return left is right
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and left.keys() == right.keys()
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return type(left) is type(right) and left == right


def _change_entries(old: Any, new: Any, path: tuple[str, ...] = ()) -> list[dict]:
    """Return the compact, old-value-free change description used for grouping."""
    if _json_equal(old, new):
        return []

    if isinstance(old, dict) and isinstance(new, dict):
        changes = []
        for key in sorted(set(old) | set(new)):
            changes.extend(
                _change_entries(
                    old.get(key, _MISSING),
                    new.get(key, _MISSING),
                    (*path, key),
                )
            )
        return changes

    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        changes = []
        for index, (old_item, new_item) in enumerate(zip(old, new)):
            changes.extend(_change_entries(old_item, new_item, (*path, f"[{index}]")))
        return changes

    if old is _MISSING:
        kind = "added"
    elif new is _MISSING:
        kind = "removed"
    else:
        kind = "changed"
    return [
        {
            "path": ".".join(path) or "(root)",
            "kind": kind,
            "newValue": {"__migrate_undefined__": True} if new is _MISSING else new,
        }
    ]


def _proposal_change_metadata(version: str, base: Any, body: Any) -> tuple[str, list[str]]:
    """Return an opaque grouping key and changed top-level sections."""
    changes = _change_entries(base, body)
    changes.sort(key=lambda item: (item["path"], item["kind"]))
    change_key = canonical_hash({"version": version, "changes": changes})

    changed_sections = []
    if isinstance(base, dict) and isinstance(body, dict):
        for key in sorted(set(base) | set(body)):
            old_value = base.get(key, _MISSING)
            new_value = body.get(key, _MISSING)
            if not _json_equal(old_value, new_value):
                changed_sections.append(key)
    return change_key, changed_sections


def proposal_summary(proposal: dict) -> dict:
    """Return queue metadata without the large base/body record snapshots."""
    change_key = proposal.get("change_key")
    changed_sections = proposal.get("changed_sections")
    if not change_key or not isinstance(changed_sections, list):
        change_key, changed_sections = _proposal_change_metadata(
            proposal.get("version"),
            proposal.get("base"),
            proposal.get("body"),
        )

    summary = {key: proposal.get(key) for key in _SUMMARY_FIELDS}
    summary["change_key"] = change_key
    summary["changed_sections"] = list(changed_sections)
    return summary


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
    change_key, changed_sections = _proposal_change_metadata(version, base, body)
    return {
        "proposal_id": str(uuid.uuid4()),
        "version": version,
        "record_id": str(record_id),
        "record_name": record_name,
        "body": body,
        "body_hash": canonical_hash(body),
        "base": base,
        "base_hash": canonical_hash(base) if base is not None else None,
        "change_key": change_key,
        "changed_sections": changed_sections,
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


def _put_proposal_s3(proposal: dict) -> None:
    """Write *proposal* to S3, overwriting any previous revision of it."""
    _s3().put_object(
        Bucket=S3_BUCKET,
        Key=_key(proposal["proposal_id"]),
        Body=json.dumps(proposal, default=str).encode(),
        ContentType="application/json",
    )


def _put_proposal_memory(proposal: dict) -> None:
    """Store *proposal* in this portal process, replacing its prior revision."""
    with _MEMORY_LOCK:
        _MEMORY_PROPOSALS[str(proposal["proposal_id"])] = _copy_proposal(proposal)


def put_proposal(proposal: dict) -> None:
    """Store *proposal* using the configured backend."""
    if METADATA_PROPOSALS_BACKEND == "memory":
        _put_proposal_memory(proposal)
        return
    _put_proposal_s3(proposal)


def _get_proposal_memory(proposal_id: str) -> Optional[dict]:
    """Return a copy of a process-local proposal, if present."""
    with _MEMORY_LOCK:
        proposal = _MEMORY_PROPOSALS.get(str(proposal_id))
        return _copy_proposal(proposal) if proposal is not None else None


def _get_proposal_s3(proposal_id: str) -> Optional[dict]:
    """Return the proposal with *proposal_id* from S3, if it exists."""
    try:
        response = _s3().get_object(Bucket=S3_BUCKET, Key=_key(proposal_id))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(response["Body"].read().decode())


def get_proposal(proposal_id: str) -> Optional[dict]:
    """Return the proposal with *proposal_id*, or None if it does not exist."""
    if METADATA_PROPOSALS_BACKEND == "memory":
        return _get_proposal_memory(proposal_id)
    return _get_proposal_s3(proposal_id)


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


def _copy_proposal(proposal: Optional[dict]) -> Optional[dict]:
    """Copy a proposal so callers cannot mutate the stored revision directly."""
    if proposal is None:
        return None
    return json.loads(json.dumps(proposal, default=str))


def _wanted_statuses(status: Optional[str]) -> Optional[set[str]]:
    """Parse a list status filter, returning None when every status is wanted."""
    if not status or status == "all":
        return None
    return {value.strip() for value in status.split(",") if value.strip()}


def _proposal_matches(
    proposal: dict,
    *,
    wanted: Optional[set[str]],
    version: Optional[str],
    record_id: Optional[str],
) -> bool:
    """Return whether a proposal satisfies every requested list filter."""
    if wanted is not None and proposal.get("status") not in wanted:
        return False
    if version and proposal.get("version") != version:
        return False
    if record_id and str(proposal.get("record_id")) != str(record_id):
        return False
    return True


def _list_proposals_memory(
    status: Optional[str] = None,
    version: Optional[str] = None,
    record_id: Optional[str] = None,
    summary: bool = False,
) -> list:
    """Return process-local proposals matching the requested filters."""
    wanted = _wanted_statuses(status)
    with _MEMORY_LOCK:
        # Stored revisions are replaced rather than mutated, so references
        # selected under the lock remain stable while we project/copy them.
        matches = [
            proposal
            for proposal in _MEMORY_PROPOSALS.values()
            if _proposal_matches(proposal, wanted=wanted, version=version, record_id=record_id)
        ]

    matches = [proposal_summary(proposal) if summary else _copy_proposal(proposal) for proposal in matches]
    matches.sort(key=lambda proposal: proposal.get("created_at") or "", reverse=True)
    return matches


def list_proposals(
    status: Optional[str] = None,
    version: Optional[str] = None,
    record_id: Optional[str] = None,
    summary: bool = False,
) -> list:
    """Return stored proposals, newest first, filtered by the given criteria.

    ``status`` may be a single status or a comma-separated list; ``None`` (or
    the literal ``"all"``) returns every status. ``summary`` omits full record
    snapshots and returns only the queue and grouping fields.
    """
    if METADATA_PROPOSALS_BACKEND == "memory":
        return _list_proposals_memory(
            status=status,
            version=version,
            record_id=record_id,
            summary=summary,
        )

    keys = _list_keys()
    if not keys:
        return []

    wanted = _wanted_statuses(status)

    with ThreadPoolExecutor(max_workers=_LIST_WORKERS) as pool:
        proposals = [p for p in pool.map(_read_key, keys) if p]

    matches = [
        proposal
        for proposal in proposals
        if _proposal_matches(proposal, wanted=wanted, version=version, record_id=record_id)
    ]
    if summary:
        matches = [proposal_summary(proposal) for proposal in matches]
    matches.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return matches
