"""Database for the QC view application."""

import panel as pn
import pandas as pd
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


class ViewData(param.Parameterized):
    """Database for the QC view application."""

    name = param.String(default="")
    record = param.Dict(default=None, allow_None=True)
    dataframe = param.DataFrame(default=pd.DataFrame())
    status = param.DataFrame(default=None, allow_None=True)

    changes = param.DataFrame(
        default=pd.DataFrame(columns=["metric_name", "column_name", "value"]),
    )
    dirty = param.Integer(default=0, doc="Number of unsaved changes")

    def __init__(self, name: str, client: MetadataDbClient = client):
        super().__init__()
        self._client = client
        self.name = name

        self._load_record()

    def _add_change(self, metric_name: str, column_name: str, value: str):
        """Add a change to the changes DataFrame"""
        self.changes = self.changes.append(
            {
                "metric_name": metric_name,
                "column_name": column_name,
                "value": value,
            },
            ignore_index=True,
        )
        self._dirty += 1

    def _remove_change(self, metric_name: str, column_name: str):
        """Remove a change from the changes DataFrame"""
        if not self.changes.empty:
            self.changes = self.changes[
                ~((self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name))
            ]
            self._dirty -= 1

    def submit_change(self, metric_name: str, column_name: str, value: str):
        """Submit a change to the database"""

        if self.dataframe.empty:
            raise ValueError("Dataframe is not loaded")

        if metric_name not in self.dataframe["name"].values:
            raise ValueError(f"Metric {metric_name} not found in dataframe")

        if column_name not in self.dataframe.columns:
            raise ValueError(f"Column {column_name} not found in dataframe")

        # Only update if the value is different from the original value
        original_value = self.dataframe.loc[self.dataframe["name"] == metric_name, column_name].values[0]
        if value != original_value:
            # Check if the value is already in the changes DataFrame
            if not self.changes.empty:
                existing_change = self.changes[
                    (self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name)
                ]
                if not existing_change.empty:
                    # Update the existing change
                    self.changes.loc[existing_change.index[0], "value"] = value
                else:
                    self._add_change(metric_name, column_name, value)
        else:
            # If the value is the same, remove the change if it exists
            if not self.changes.empty:
                if not self.changes[
                    (self.changes["metric_name"] == metric_name) & (self.changes["column_name"] == column_name)
                ].empty:
                    self._remove_change(metric_name, column_name)

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
        # This can happen automatically if we turn everything back into dictionaries
        quality_control = self.record.get("quality_control", {})

        metrics = []
        for _, row in self.dataframe.iterrows():
            metrics.append(row.to_dict())

        quality_control["metrics"] = metrics

        return QualityControl(**quality_control)

    @property
    def default_grouping(self) -> list:
        """Get the default grouping for this record"""
        if self.dataframe.empty:
            return []

        qc = self.get_quality_control()
        return qc.default_grouping

    @property
    def grouping_options(self) -> list:
        """Get the grouping options for this record: all modalities and tags"""
        if self.dataframe.empty:
            return []

        qc = self.get_quality_control()

        # Get all the modalities and tags
        modalities = [m.abbreviation for m in qc.modalities]
        tags = qc.default_grouping

        return modalities + tags

    @pn.depends("dataframe", watch=True)
    def _compute_status(self):
        """Compute the status for modalities, stages, and default_grouping tags"""
        statuses = []

        # Get all the relevant tags
        qc = self.get_quality_control()

        modalities = qc.modalities
        stages = qc.stages
        default_grouping = qc.default_grouping

        # For each stage, compute the status of each modality and grouping tag
        for stage in stages:
            for modality in modalities:
                cstatus = qc.evaluate_status(
                    stage=stage,
                    modality=modality,
                )
                statuses.append(
                    {
                        "stage": stage,
                        "tag": modality.abbreviation,
                        "status": cstatus.value,
                    }
                )

            for tag in default_grouping:
                cstatus = qc.evaluate_status(
                    stage=stage,
                    modality=None,
                    tag=tag,
                )
                statuses.append(
                    {
                        "stage": stage,
                        "tag": tag,
                        "status": cstatus.value,
                    }
                )

        # Re-organize the DataFrame from long form to wide, with stage as rows and tags as columns
        self.status = pd.DataFrame(statuses).pivot(index="stage", columns="tag", values="status")
        self.status.columns.name = None
        self.status.reset_index(inplace=True)

    # @pn.cache(max_items=1000, policy="LFU")
    def _load_record(self):
        """Get a QualityControl object from the database by its name."""
        records = client.retrieve_docdb_records(
            filter_query={
                "name": self.name,
            },
            projection={
                "_id": 1,
                "quality_control": 1,
                "name": 1,
                "location": 1,
                "data_description.project_name": 1,
            },
        )

        if not records:
            return

        self.record = records[0]
        quality_control = self.record.get("quality_control", {})

        self.dataframe = (
            pd.DataFrame(quality_control["metrics"]) if quality_control and "metrics" in quality_control else None
        )
