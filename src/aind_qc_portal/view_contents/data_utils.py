"""Utility functions for handling data/metadata from assets """


from datetime import datetime
import json

import panel as pn


def encode_dict_value(value):
    """Encode a dict value as a JSON string with 'json:' prefix."""
    if isinstance(value, dict):
        return f"json:{json.dumps(value)}"
    return value


def decode_dict_value(value):
    """Decode a 'json:' prefixed string back to a dict."""
    if isinstance(value, str) and value.startswith("json:"):
        return json.loads(value[5:])  # Remove 'json:' prefix and parse
    return value


def upload_temporary_metadata(metadata: dict):
    """Upload metadata to the database."""
    if not hasattr(pn.state, "metadata"):
        pn.state.metadata = {}
    pn.state.metadata[metadata["name"]] = metadata

    print(f"Uploaded temporary metadata for {metadata['name']}")
    print(f"Full data: {metadata}")


def create_curation_history_entry(curator: str) -> dict:
    """Create a curation history entry.

    Args:
        curator: Name of the curator

    Returns:
        Dict with object_type, curator, and timestamp
    """
    return {
        "object_type": "Curation history",
        "curator": curator,
        "timestamp": datetime.now().isoformat(),
    }


def create_status_history_entry(status: str, evaluator: str) -> dict:
    """Create a status history entry.

    Args:
        status: Status value (Pass, Fail, Pending)
        evaluator: Name of the evaluator

    Returns:
        Dict with status, evaluator, and timestamp
    """
    return {
        "status": status,
        "evaluator": evaluator,
        "timestamp": datetime.now().isoformat(),
    }


def apply_curation_metric_change(metric_obj: dict, value_change: any, curator: str) -> None:
    """Apply a value change to a curation metric in-place.

    Args:
        metric_obj: The metric dictionary to modify
        value_change: The new value to append
        curator: Name of the curator
    """
    # Ensure value exists and is a list
    if "value" not in metric_obj or not isinstance(metric_obj["value"], list):
        metric_obj["value"] = []

    # Append new value as JSON string
    metric_obj["value"].append(json.dumps(value_change))

    # Add curation history entry
    if "curation_history" not in metric_obj:
        metric_obj["curation_history"] = []
    metric_obj["curation_history"].append(create_curation_history_entry(curator))


def apply_qc_metric_change(metric_obj: dict, value_change: any) -> None:
    """Apply a value change to a regular QC metric in-place.

    Args:
        metric_obj: The metric dictionary to modify
        value_change: The new value to set
    """
    metric_obj["value"] = value_change


def apply_status_change(metric_obj: dict, status_change: str, evaluator: str) -> None:
    """Apply a status change to a metric in-place.

    Args:
        metric_obj: The metric dictionary to modify
        status_change: The new status value
        evaluator: Name of the evaluator
    """
    # Ensure status_history exists
    if "status_history" not in metric_obj:
        metric_obj["status_history"] = []

    metric_obj["status_history"].append(create_status_history_entry(status_change, evaluator))
