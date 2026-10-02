"""Mutation and hashing primitives for the tenant-authenticated QC submit API.

This module implements the tenant-authenticated QC submit contract. It reuses
the same mutation helpers as the Panel app's
write path (`view_contents/data_utils.py`) so the two writers apply metric
value/status/curation/notes changes identically.

`canonical_qc_json`/`qc_hash` must stay byte-for-byte in sync with the
JavaScript implementation in zombie's `web/src/qc/canonical.js` — both sides
implement JCS-SHA256-v1 and have to hash the exact same bytes for the
stale-record check to mean anything. Cross-language fixtures live in
`web/src/qc/canonical-fixtures.js` and are mirrored in
`tests/test_qc_edit.py`.
"""

import copy
import hashlib
import json
import re

from aind_data_schema.core.quality_control import Status

from aind_qc_portal.view_contents.data_utils import (
    apply_curation_metric_change,
    apply_notes_change,
    apply_qc_metric_change,
    apply_status_change,
    create_status_history_entry,
    recompute_qc_status,
)


class QcEditError(Exception):
    """Raised when a QC edit request is malformed or fails schema validation.

    The caller inspects the message for the substring "schema validation" to
    distinguish a 422 (invalid QC data) from a 400 (malformed request).
    """


class QcEditWriteError(Exception):
    """Raised when DocDB rejects the QC write."""


class QcEditStale(Exception):
    """Raised when the record changed between the client's read and the write."""


class QcEditTargetMismatch(Exception):
    """Raised when the record fetched is not the record the request named."""


class _Missing:
    """Sentinel distinguishing "notes omitted" from "notes explicitly set"."""

    def __repr__(self):
        return "MISSING"


MISSING = _Missing()

_SUPPORTED_STATUSES = {status.value for status in Status}
_ALLOWED_CHANGE_FIELDS = {"metric_name", "value", "status", "delete_curation_indices"}
_ALLOWED_NEW_METRIC_FIELDS = {"name", "modality", "stage", "value", "description", "reference", "tags"}
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def is_qc_hash(value) -> bool:
    """Return True if `value` looks like a canonical QC sha256 hex digest."""
    return isinstance(value, str) and bool(_HEX64_RE.fullmatch(value))


def _canonical_number(value) -> str:  # noqa: C901
    """Render `value` the way ECMAScript's Number::toString would.

    Mirrors `canonicalNumber` in web/src/qc/canonical.js: extract the
    shortest-round-trip significant digits and decimal exponent, then choose
    fixed vs. exponential notation using the exact same thresholds JS uses.
    Python's `repr(float)` and JS's `Number.prototype.toString()` both
    produce the shortest round-trip decimal digit sequence for a given
    float64, so re-deriving digits/exponent from `repr()` and reformatting
    with JS's rules yields an identical string.
    """
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("QC hash cannot encode non-finite numbers")
    if value == 0:
        return "0"

    text = repr(value).lower()
    sign = ""
    if text.startswith("-"):
        sign = "-"
        text = text[1:]

    if "e" in text:
        mantissa, exponent_text = text.split("e")
        exponent = int(exponent_text)
    else:
        mantissa, exponent = text, 0

    if "." in mantissa:
        whole, fraction = mantissa.split(".")
    else:
        whole, fraction = mantissa, ""
    # Python's repr always shows a decimal point for floats (e.g. "1.0"); a
    # lone "0" fraction is that formatting artifact, not a significant digit.
    if fraction == "0":
        fraction = ""

    digits = (whole + fraction).lstrip("0") or "0"
    whole_digits = whole.lstrip("0")
    if whole_digits:
        decimal_exponent = exponent + len(whole_digits) - 1
    else:
        leading_fraction_zeroes = len(fraction) - len(fraction.lstrip("0"))
        decimal_exponent = exponent - leading_fraction_zeroes - 1
    if digits == "0":
        return "0"

    if -6 <= decimal_exponent < 21:
        position = decimal_exponent + 1
        if position <= 0:
            return f"{sign}0.{'0' * -position}{digits}"
        if position >= len(digits):
            return f"{sign}{digits}{'0' * (position - len(digits))}"
        return f"{sign}{digits[:position]}.{digits[position:]}"

    rest = digits[1:].rstrip("0")
    coefficient = f"{digits[0]}.{rest}" if rest else digits[0]
    exponent_sign = "+" if decimal_exponent >= 0 else "-"
    return f"{sign}{coefficient}e{exponent_sign}{abs(decimal_exponent)}"


def _utf16_sort_key(value: str) -> bytes:
    """Return the UTF-16 code-unit sequence used by RFC 8785 property sorting."""
    return value.encode("utf-16-be", "surrogatepass")


def canonical_qc_json(value) -> str:
    """Serialize `value` to the frozen canonical JSON used for QC hashing.

    Keep in sync with `canonicalQcJson` in web/src/qc/canonical.js. This is
    JCS-SHA256-v1: recursive objects sorted by UTF-16 code units,
    JSON-string-escaped keys/strings (non-ASCII left literal, matching JS's
    `JSON.stringify`), and ECMAScript-style numbers.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _canonical_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_qc_json(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("QC hash object keys must be strings")
        keys = sorted(value.keys(), key=_utf16_sort_key)
        parts = (f"{json.dumps(key, ensure_ascii=False)}:{canonical_qc_json(value[key])}" for key in keys)
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"Unsupported value in QC hash: {type(value)!r}")


def qc_hash(value) -> str:
    """Return the sha256 hex digest of `value`'s canonical QC JSON."""
    canonical = canonical_qc_json(value)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_change(change) -> None:
    if not isinstance(change, dict):
        raise QcEditError("each change must be an object")
    unknown_fields = set(change) - _ALLOWED_CHANGE_FIELDS
    if unknown_fields:
        raise QcEditError(f"unsupported change field(s): {sorted(unknown_fields)}")
    name = change.get("metric_name")
    if not isinstance(name, str) or not name:
        raise QcEditError("metric_name is required")
    if "value" not in change and "status" not in change and "delete_curation_indices" not in change:
        raise QcEditError(f"change for {name!r} has no value, status, or curation deletion")
    if "status" in change and change["status"] not in _SUPPORTED_STATUSES:
        raise QcEditError(f"unsupported status: {change['status']!r}")
    if "delete_curation_indices" in change:
        indices = change["delete_curation_indices"]
        if (
            not isinstance(indices, list)
            or not indices
            or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in indices)
            or len(set(indices)) != len(indices)
        ):
            raise QcEditError("delete_curation_indices must be a non-empty list of unique non-negative integers")


def _build_new_metric(metric, actor: str) -> dict:
    """Return a plain QC metric whose only status is a Pending entry by `actor`.

    Clients cannot supply status history, curation fields, or object_type, so a
    new metric can never arrive already evaluated or impersonating another user.
    """
    if not isinstance(metric, dict):
        raise QcEditError("each added metric must be an object")
    unknown_fields = set(metric) - _ALLOWED_NEW_METRIC_FIELDS
    if unknown_fields:
        raise QcEditError(f"unsupported added metric field(s): {sorted(unknown_fields)}")
    name = metric.get("name")
    if not isinstance(name, str) or not name:
        raise QcEditError("added metric name is required")
    if "value" not in metric:
        raise QcEditError(f"added metric {name!r} has no value")
    return {
        "object_type": "QC metric",
        **copy.deepcopy(metric),
        "status_history": [
            {"object_type": "QC status", **create_status_history_entry(Status.PENDING.value, actor)}
        ],
    }


def _delete_curation_entries(metric_obj: dict, indices: list) -> None:
    """Remove selected curation values and their aligned history entries."""
    values = metric_obj.get("value", [])
    if isinstance(values, str):
        try:
            values = json.loads(values[5:] if values.startswith("json:") else values)
        except json.JSONDecodeError as exc:
            raise QcEditError("curation metric value is not valid JSON") from exc
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, list):
        raise QcEditError("curation metric value must be a list")
    if any(index >= len(values) for index in indices):
        raise QcEditError("delete_curation_indices contains an index outside the curation history")

    deleted = set(indices)
    metric_obj["value"] = [value for index, value in enumerate(values) if index not in deleted]

    history = metric_obj.get("curation_history")
    if isinstance(history, list):
        metric_obj["curation_history"] = [entry for index, entry in enumerate(history) if index not in deleted]


def apply_qc_changes(  # noqa: C901
    record: dict, changes: list, *, actor: str, notes=MISSING, add_metrics=None
) -> dict:
    """Return a deep-copied, mutated, schema-validated record.

    Applies each change using the same primitives as the Panel write path
    (`apply_qc_metric_change`, `apply_curation_metric_change`,
    `apply_status_change`, `apply_notes_change`): a regular metric's value is
    replaced, a curation metric can have selected history entries removed and
    new values appended, and any status change appends a status-history entry.
    `add_metrics` appends new plain QC metrics (see `_build_new_metric`) before
    `changes` are applied; a name that already exists is rejected.
    `actor` is used as both evaluator and curator; it must already be the
    server-verified identity, never a client-supplied name. Raises
    `QcEditError` — with "schema validation" in the message for a schema
    failure, otherwise not — on any invalid input.
    """
    if not isinstance(changes, list):
        raise QcEditError("changes must be a list")

    new_record = copy.deepcopy(record)
    quality_control = new_record.get("quality_control")
    if not isinstance(quality_control, dict):
        raise QcEditError("record has no quality_control section")
    metrics = quality_control.get("metrics")
    if not isinstance(metrics, list):
        raise QcEditError("quality_control.metrics is not a list")

    metrics_by_name = {}
    for metric in metrics:
        name = metric.get("name")
        if name is not None and name not in metrics_by_name:
            metrics_by_name[name] = metric

    if add_metrics is not None:
        if not isinstance(add_metrics, list):
            raise QcEditError("add_metrics must be a list")
        for metric in add_metrics:
            new_metric = _build_new_metric(metric, actor)
            if new_metric["name"] in metrics_by_name:
                raise QcEditError(f"metric already exists: {new_metric['name']}")
            metrics.append(new_metric)
            metrics_by_name[new_metric["name"]] = new_metric

    seen_names = set()
    for change in changes:
        _validate_change(change)
        name = change["metric_name"]
        if name in seen_names:
            raise QcEditError(f"duplicate metric_name: {name}")
        seen_names.add(name)

        metric_obj = metrics_by_name.get(name)
        if metric_obj is None:
            raise QcEditError(f"unknown metric_name: {name}")

        if "delete_curation_indices" in change:
            if metric_obj.get("object_type") != "Curation metric":
                raise QcEditError(f"metric {name!r} is not a curation metric")
            _delete_curation_entries(metric_obj, change["delete_curation_indices"])
        if "value" in change:
            if metric_obj.get("object_type") == "Curation metric":
                apply_curation_metric_change(metric_obj, change["value"], actor)
            else:
                apply_qc_metric_change(metric_obj, change["value"])
        if "status" in change:
            apply_status_change(metric_obj, change["status"], actor)

    if notes is not MISSING:
        if not isinstance(notes, str):
            raise QcEditError("notes must be a string")
        apply_notes_change(new_record, notes)

    try:
        recompute_qc_status(quality_control)
    except Exception as exc:
        raise QcEditError(f"schema validation failed: {exc}") from exc

    return new_record


def verify_write_target(record, record_id: str, expected_qc_hash: str) -> None:
    """Raise unless `record` is the record we intend to write and is unchanged.

    The `_id` check is what keeps `_upsert_one_record`'s hardcoded
    `upsert: True` from inserting a new document: a filter on an `_id` that
    is not the one we actually read would miss and insert rather than update.
    """
    if record is None:
        raise QcEditStale("The QC record no longer exists")
    actual_id = record.get("_id")
    if actual_id is None or str(actual_id) != str(record_id):
        raise QcEditTargetMismatch(f"Fetched record _id does not match the requested record_id {record_id!r}")
    if qc_hash(record.get("quality_control")) != expected_qc_hash:
        raise QcEditStale("The QC record changed")


def update_qc_record(client, record_id: str, new_quality_control):
    """Write `new_quality_control` onto the record with `_id == record_id`.

    Filters on `_id` alone. `_upsert_one_record` hardcodes `upsert: True`, so
    a filter that matches nothing inserts rather than no-ops; `_id` is the
    only field with a database-enforced unique index, which turns a miss into
    a duplicate-key error instead of a silently forked duplicate record.
    Callers must confirm the `_id` came from a record they actually read --
    see `verify_write_target`.

    Only the `quality_control` subtree is `$set`, so a concurrent edit to an
    unrelated part of the record is preserved.
    """
    if not isinstance(record_id, str) or not record_id:
        raise QcEditWriteError("record_id must be a non-empty string")
    canonical_new = json.loads(json.dumps(new_quality_control, default=str))
    response = client._upsert_one_record(
        record_filter={"_id": record_id},
        update={"$set": {"quality_control": canonical_new}},
    )
    status_code = getattr(response, "status_code", 200)
    if status_code not in (200, 201):
        raise QcEditWriteError(f"Unexpected DocDB response status {status_code}")
    return response
