"""Database for the QC view application."""

import json
from datetime import datetime

import pandas as pd
import panel as pn
import param
from aind_data_access_api.document_db import MetadataDbClient
from aind_data_schema.core.quality_control import QualityControl

TIMEOUT_1M = 60
TIMEOUT_1H = 60 * 60
TIMEOUT_24H = 60 * 60 * 24

client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)


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


class ViewData(param.Parameterized):
    """Database for the QC view application."""

    asset_name = param.String(default="")
    record = param.Dict(default=None, allow_None=True)
    dataframe = param.DataFrame(default=pd.DataFrame())
    metric_status = param.DataFrame(default=pd.DataFrame())

    changes = param.DataFrame(
        default=pd.DataFrame(columns=["metric_name", "column_name", "value"]),
    )

    def __init__(self, asset_name: str, client: MetadataDbClient = client):
        """Initialize ViewData with asset name and metadata client"""
        super().__init__()
        self._client = client
        self.asset_name = asset_name

        self._load_record()
        self._parse_record()
        self.load_changes_from_cache()

    @property
    def s3_bucket(self) -> str:
        """Get the S3 bucket for this record"""
        return self._s3_bucket if hasattr(self, "_s3_bucket") else ""

    @property
    def s3_prefix(self) -> str:
        """Get the S3 prefix for this record"""
        return self._s3_prefix if hasattr(self, "_s3_prefix") else ""

    @property
    def raw_s3_location(self) -> str:
        """Get the S3 location for the raw asset associated with this record"""
        return (
            f"s3://{self._raw_s3_bucket}/{self._raw_s3_prefix}"
            if hasattr(self, "_raw_s3_bucket") and hasattr(self, "_raw_s3_prefix")
            else ""
        )

    def _add_change(self, metric_name: str, column_name: str, value: str):
        """Add a change to the changes DataFrame"""
        new_row = pd.DataFrame(
            [
                {
                    "metric_name": metric_name,
                    "column_name": column_name,
                    "value": value,
                }
            ]
        )
        self.changes = pd.concat([self.changes, new_row], ignore_index=True)

    def _remove_change(self, metric_name: str, column_name: str):
        """Remove a change from the changes DataFrame"""
        if not self.changes.empty:
            self.changes = self.changes[
                ~((self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name))
            ]

    def _get_original_value(self, metric_name: str, column_name: str):
        """Get the original value from the dataframe for a given metric and column"""
        if self.dataframe.empty:
            raise ValueError("Dataframe is not loaded")

        if metric_name not in self.dataframe["name"].values:
            raise ValueError(f"Metric {metric_name} not found in dataframe")

        if column_name == "status":
            status_history = self.dataframe.loc[self.dataframe["name"] == metric_name, "status_history"].values[0]
            original_value = status_history[-1].get("status", "Pending") if status_history else "Pending"
        else:
            if column_name not in self.dataframe.columns:
                raise ValueError(f"Column {column_name} not found in dataframe")
            original_value = self.dataframe.loc[self.dataframe["name"] == metric_name, column_name].values[0]

        return original_value

    def submit_change(self, metric_name: str, column_name: str, value: str):
        """Submit a change to the database (stores in pending changes, does not modify original data)"""

        original_value = self._get_original_value(metric_name, column_name)

        # Convert Status enum to string if needed
        if hasattr(value, "value"):
            value = value.value

        # Encode the value for comparison (to match how it's stored in dataframe)
        encoded_value = encode_dict_value(value)

        # Check if this change reverts to the original value
        if encoded_value == original_value:
            # Remove the change if it exists
            if not self.changes.empty:
                existing_change = self.changes[
                    (self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name)
                ]
                if not existing_change.empty:
                    self._remove_change(metric_name, column_name)

            # Update metric_status to reflect reversion to original
            if column_name == "status":
                self.metric_status.loc[self.metric_status["name"] == metric_name, "evaluated_status"] = original_value
            return

        # Value differs from original - add or update the change
        if not self.changes.empty:
            existing_change = self.changes[
                (self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name)
            ]
            if not existing_change.empty:
                self.changes.loc[existing_change.index[0], "value"] = encoded_value
            else:
                self._add_change(metric_name, column_name, encoded_value)
        else:
            self._add_change(metric_name, column_name, encoded_value)

        # Update metric_status to reflect pending change
        if column_name == "status":
            self.metric_status.loc[self.metric_status["name"] == metric_name, "evaluated_status"] = value

        # Save changes to cache
        self.save_changes_to_cache()

    @property
    def default_grouping(self) -> list:
        """Get the default grouping for this record"""
        if self.dataframe.empty:
            print("[ViewData.default_grouping] Dataframe is empty, returning []")
            return []

        # Unwrap any tuples of length 1 into just string
        default_grouping = self.record["quality_control"].get("default_grouping", [])
        for i, level in enumerate(default_grouping):
            if isinstance(level, tuple) and len(level) == 1:
                default_grouping[i] = level[0]

        return default_grouping

    @property
    @pn.cache()
    def grouping_options(self) -> tuple[list, list]:
        """Get the grouping options for this record: all modalities and tags"""
        if self.dataframe.empty:
            return []

        modalities = self.dataframe["modality"]
        modalities = [
            modality["abbreviation"]
            for modality in modalities
            if isinstance(modality, dict) and "abbreviation" in modality
        ]
        modalities = list(set(modalities))

        stages = self.dataframe["stage"]
        stages = [stage for stage in stages if isinstance(stage, str)]
        stages = list(set(stages))

        tags = self.dataframe["tags"]
        tags = [list(decode_dict_value(tag_dict).keys()) for tag_dict in tags if isinstance(tag_dict, str)]
        tags = [tag for sublist in tags for tag in sublist]  # Flatten list of lists
        tags = list(set(tags))

        return (modalities, stages + tags)

    def _load_record(self):
        """Get a QualityControl object from the database by its name."""

        # First try to pull record from DocDB
        records = client.retrieve_docdb_records(
            filter_query={
                "name": self.asset_name,
            },
            projection={
                "_id": 1,
                "quality_control": 1,
                "name": 1,
                "location": 1,
                "other_identifiers": 1,
                "data_description.project_name": 1,
                "data_description.source_data": 1,
            },
        )

        if not records:
            if hasattr(pn.state, "metadata") and self.asset_name in pn.state.metadata:
                self.record = pn.state.metadata[self.asset_name]
                print(f"Loaded record {self.asset_name} from temporary metadata")
            else:
                print(f"Failed to load {self.asset_name} from local or DocDB")
                return
        else:
            self.record = records[0]

        quality_control = self.record.get("quality_control", {})

        if not quality_control or "metrics" not in quality_control:
            return

        # Encode dict values as JSON strings for cleaner dataframe storage
        metrics_copy = []
        for metric in quality_control["metrics"]:
            metric_copy = metric.copy()

            # Encode any dict values (including nested dicts in 'value' field)
            metric_copy["value"] = encode_dict_value(metric_copy["value"])
            metric_copy["tags"] = encode_dict_value(metric_copy["tags"])

            metrics_copy.append(metric_copy)

        # Create dataframe from records - dicts are now stored as JSON strings
        self.dataframe = pd.DataFrame.from_records(metrics_copy)

        # Compute the evaluated status for each metric
        self._compute_metric_statuses()

    def _compute_metric_statuses(self):
        """Compute the evaluated status for each metric using the metric's status_history"""
        if self.dataframe.empty:
            return

        # Build a separate status dataframe with metric name and evaluated status
        status_data = []
        for _, row in self.dataframe.iterrows():
            # Get the current status from the metric's status_history
            status_history = row.get("status_history", [])
            if status_history:
                current_status = status_history[-1].get("status", "Pending")
            else:
                current_status = "Pending"

            status_data.append({"name": row.get("name"), "evaluated_status": current_status})

        self.metric_status = pd.DataFrame(status_data)

    def _parse_record(self):
        """Parse the record and cache some data for faster access."""
        if self.record and "location" in self.record:
            location = self.record["location"].replace("s3://", "")
            self._s3_bucket, self._s3_prefix = location.split("/", 1)

        if self.record and "data_description" in self.record:
            data_description = self.record["data_description"]
            if "source_data" in data_description and data_description["source_data"]:
                self._raw_asset_name = data_description["source_data"][0]

                # Pull the raw record to get its S3 location
                raw_records = client.retrieve_docdb_records(
                    filter_query={
                        "name": self._raw_asset_name,
                    },
                    projection={
                        "location": 1,
                    },
                )

                if raw_records:
                    raw_location = raw_records[0]["location"].replace("s3://", "")
                    self._raw_s3_bucket, self._raw_s3_prefix = raw_location.split("/", 1)

    @property
    def _cache_key(self) -> tuple[str, str]:
        """Get the cache key for this user and asset."""
        username = pn.state.user if hasattr(pn.state, "user") and pn.state.user != "guest" else None
        return (username, self.asset_name) if username else (None, None)

    def save_changes_to_cache(self):
        """Save pending changes to pn.state.cache."""
        username, asset_name = self._cache_key
        if not username:
            return

        if not hasattr(pn.state, "cache"):
            pn.state.cache = {}

        if username not in pn.state.cache:
            pn.state.cache[username] = {}

        pn.state.cache[username][asset_name] = self.changes.to_dict(orient="records")

    def load_changes_from_cache(self):
        """Load pending changes from pn.state.cache if available."""
        username, asset_name = self._cache_key
        if not username:
            return

        if not hasattr(pn.state, "cache"):
            return

        if username in pn.state.cache and asset_name in pn.state.cache[username]:
            cached_changes = pn.state.cache[username][asset_name]
            if cached_changes:
                # Convert back to DataFrame and apply changes using submit_change
                for change in cached_changes:
                    self.submit_change(
                        change["metric_name"],
                        change["column_name"],
                        decode_dict_value(change["value"]),
                    )

    def clear_changes_cache(self):
        """Clear pending changes from both DataFrame and cache."""
        username, asset_name = self._cache_key

        # Clear the changes DataFrame
        self.changes = pd.DataFrame(columns=["metric_name", "column_name", "value"])

        # Clear from cache if exists
        if username and hasattr(pn.state, "cache"):
            if username in pn.state.cache and asset_name in pn.state.cache[username]:
                del pn.state.cache[username][asset_name]

    def get_fresh_record(self) -> dict:
        """Re-pull the full record from DocDB as a dict."""
        records = self._client.retrieve_docdb_records(
            filter_query={"name": self.asset_name},
            projection={},  # Get all fields
        )

        if not records:
            if hasattr(pn.state, "metadata") and self.asset_name in pn.state.metadata:
                return pn.state.metadata[self.asset_name]
            raise ValueError(f"Record {self.asset_name} not found in DocDB or temporary storage")

        return records[0]

    def get_submission_data(self) -> tuple[pd.DataFrame, dict]:  # noqa: C901
        """Build a dataframe for the submission preview table.

        Uses a fresh copy of the record from DocDB

        Returns a dataframe with columns:
        - metric_name: name of the metric
        - current_value: current value
        - current_status: current status
        - new_value: new value (if changed)
        - new_status: new status (if changed)
        - has_changes: whether this row has changes
        """
        if self.dataframe.empty:
            return pd.DataFrame()

        record = self.get_fresh_record()
        metrics = record["quality_control"]["metrics"]

        preview_data = []

        for i, metric in enumerate(metrics):
            name = metric["name"]

            # Get current values
            current_value = metric["value"]
            if isinstance(current_value, dict) and "value" in current_value:
                current_value = current_value["value"]
            status_history = metric.get("status_history", [])
            current_status = status_history[-1].get("status", "Pending") if status_history else "Pending"

            # Check for pending changes
            value_change = None
            status_change = None
            has_changes = False

            if not self.changes.empty:
                metric_changes = self.changes[self.changes["metric_name"] == name]

                for _, change_row in metric_changes.iterrows():
                    column_name = change_row["column_name"]
                    new_val = decode_dict_value(change_row["value"])

                    if column_name == "value":
                        value_change = new_val
                        has_changes = True
                    elif column_name == "status":
                        status_change = new_val
                        has_changes = True

            if value_change:
                if isinstance(value_change, dict) and "value" in value_change:
                    value_change_display = value_change["value"]
                else:
                    value_change_display = value_change

            preview_data.append(
                {
                    "metric_name": name,
                    "current_value": str(current_value),
                    "current_status": current_status,
                    "new_value": value_change_display if value_change is not None else "",
                    "new_status": status_change if status_change is not None else "",
                    "has_changes": has_changes,
                }
            )

            # Also modify the record in-place to reflect pending changes
            if has_changes:
                metric_obj = record["quality_control"]["metrics"][i]
                is_curation_metric = metric_obj.get("object_type") == "Curation metric"

                # Get current user/curator
                current_user = pn.state.user if hasattr(pn.state, "user") and pn.state.user != "guest" else "unknown"

                if value_change is not None:
                    if is_curation_metric:
                        apply_curation_metric_change(metric_obj, value_change, current_user)
                    else:
                        apply_qc_metric_change(metric_obj, value_change)

                if status_change is not None:
                    apply_status_change(metric_obj, status_change, current_user)

        preview_df = pd.DataFrame(preview_data)
        # Sort so changed rows appear first
        preview_df = preview_df.sort_values(by="has_changes", ascending=False)

        return preview_df, record

    def submit_changes_to_docdb(self, new_record) -> tuple[bool, str]:
        """Apply pending changes to the record and submit to DocDB.

        Returns:
            tuple of (success: bool, message: str)
        """
        try:
            # Step 1: Validate with QualityControl model
            try:
                QualityControl.model_validate(new_record["quality_control"])
            except Exception as e:
                return False, f"Validation failed: {str(e)}"

            # Step 2: Upsert to DocDB
            try:
                response = self._client.upsert_one_docdb_record(new_record)

                # Check response
                if hasattr(response, "status_code") and response.status_code != 200:
                    return False, f"DocDB upsert failed with status {response.status_code}: {response.text}"

                # Clear changes on success
                self.clear_changes_cache()

                return True, "Changes submitted successfully"

            except Exception as e:
                return False, f"DocDB upsert error: {str(e)}"

        except Exception as e:
            return False, f"Error during submission: {str(e)}"
