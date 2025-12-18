"""Database for the QC view application."""

import json
import pandas as pd
import panel as pn
import param
from aind_data_access_api.document_db import MetadataDbClient
from aind_data_schema.core.quality_control import QualityControl, QCMetric, CurationMetric

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

    def submit_change(self, metric_name: str, column_name: str, value: str):
        """Submit a change to the database (stores in pending changes, does not modify original data)"""

        if self.dataframe.empty:
            raise ValueError("Dataframe is not loaded")

        if metric_name not in self.dataframe["name"].values:
            raise ValueError(f"Metric {metric_name} not found in dataframe")

        # Get the original value from the dataframe
        if column_name == "status":
            status_history = self.dataframe.loc[self.dataframe["name"] == metric_name, "status_history"].values[0]
            original_value = status_history[-1].get("status", "Pending") if status_history else "Pending"
        else:
            if column_name not in self.dataframe.columns:
                raise ValueError(f"Column {column_name} not found in dataframe")
            original_value = self.dataframe.loc[self.dataframe["name"] == metric_name, column_name].values[0]

        # Convert Status enum to string if needed
        if hasattr(value, 'value'):
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

    def upsert_quality_control(self):
        """Upsert the quality control data to the database including all pending changes."""

        # Write the pending changes
        for _, change in self.changes.iterrows():
            metric_name = change["metric_name"]
            column_name = change["column_name"]
            value = change["value"]

            # Update the dataframe with the new value
            self.dataframe.loc[self.dataframe["name"] == metric_name, column_name] = value

        self.changes.clear()

        # Unwrap the dataframe back into a QualityControl object
        qc = self.get_quality_control()

        # Upsert
        client.upsert_one_docdb_record(
            record={
                "_id": self.record["_id"],
                "quality_control": qc.model_dump(),
            }
        )

    def get_quality_control(self):
        """Get the quality control data from the database."""
        if self.dataframe.empty:
            return None

        # Each row in the dataframe should be rebuilt as either a QCMetric or CurationMetric
        quality_control = self.record.get("quality_control", {})

        metrics = []
        for _, row in self.dataframe.iterrows():
            metric_dict = row.to_dict()
            
            # Decode any JSON-encoded values back to dicts
            for key, value in metric_dict.items():
                metric_dict[key] = decode_dict_value(value)
            
            if "object_type" in metric_dict:
                if metric_dict["object_type"] == "QC metric":
                    # Remove dataframe columns that are not part of the QCMetric model
                    if "evaluated_assets" in metric_dict:
                        metric_dict.pop("evaluated_assets")
                    if "curation_history" in metric_dict:
                        metric_dict.pop("curation_history")
                    if "type" in metric_dict:
                        metric_dict.pop("type")
                    metrics.append(QCMetric(**metric_dict))
                elif metric_dict["object_type"] == "Curation metric":
                    metrics.append(CurationMetric(**metric_dict))
                else:
                    raise ValueError(f"Unknown metric object_type: {metric_dict['object_type']}")
            else:
                raise ValueError("Metric dictionary missing 'object_type' field")

        quality_control["metrics"] = metrics

        return QualityControl(**quality_control)

    @property
    def default_grouping(self) -> list:
        """Get the default grouping for this record"""
        if self.dataframe.empty:
            print("[ViewData.default_grouping] Dataframe is empty, returning []")
            return []

        qc = self.get_quality_control()
        print(f"[ViewData.default_grouping] Retrieved from QC: {qc.default_grouping}")
        # Unwrap any tuples of length 1 into just string
        default_grouping = qc.default_grouping
        for i, level in enumerate(default_grouping):
            if isinstance(level, tuple) and len(level) == 1:
                default_grouping[i] = level[0]

        return default_grouping

    @property
    def grouping_options(self) -> list:
        """Get the grouping options for this record: all modalities and tags"""
        if self.dataframe.empty:
            return []

        qc = self.get_quality_control()

        # Get all the modalities and tags
        modalities = [m.abbreviation for m in qc.modalities]
        tags = []
        for metric in qc.metrics:
            metric_tags = metric.tags if metric.tags else {}
            for tag_key in metric_tags.keys():
                if tag_key not in tags:
                    tags.append(tag_key)
        tags = list(set(tags))  # Unique tags

        return modalities + tags

    # @pn.cache(max_items=1000, policy="LFU")
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
                "data_description.modalities": 1,
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
            metric_copy['value'] = encode_dict_value(metric_copy['value'])
            metric_copy['tags'] = encode_dict_value(metric_copy['tags'])
            
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
