"""Database for the QC view application."""

from typing import Optional

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

    name = param.String(default=None, allow_None=True)
    dataframe = param.DataFrame(default=None, allow_None=True)

    dirty = param.Integer(default=0, doc="Number of unsaved changes")

    def __init__(self, name: str, client: MetadataDbClient = client):
        super().__init__()
        self._client = client
        self.name = name

        self._load_record()
        print(self.dataframe)

    def submit_change(self, metric_name: str, column_name: str, value: str):
        """Submit a change to the database"""

        if not self._dataframe:
            raise ValueError("Dataframe is not loaded")

        if metric_name not in self._dataframe["name"].values:
            raise ValueError(f"Metric {metric_name} not found in dataframe")

        if column_name not in self._dataframe.columns:
            raise ValueError(f"Column {column_name} not found in dataframe")

        # Only update if the value has changed
        if value != self._dataframe.loc[self._dataframe["name"] == metric_name, column_name].values[0]:
            self._dataframe.loc[self._dataframe["name"] == metric_name, column_name] = value
            self._dirty += 1

    def get_quality_control(self):
        """Get the quality control data from the database."""
        if not self._dataframe:
            raise ValueError("Dataframe is not loaded")

        # Each row in the dataframe should be rebuilt as either a QCMetric or CurationMetric
        # This can happen automatically if we turn everything back into dictionaries
        quality_control = self.record.get("quality_control", {})

        metrics = []
        for _, row in self._dataframe.iterrows():
            metrics.append(row.to_dict())

        quality_control["metrics"] = metrics

        return QualityControl(**quality_control)

    # @pn.cache(max_items=1000, policy="LFU")
    def _load_record(self):
        """Get a QualityControl object from the database by its name.
        """
        records = client.retrieve_docdb_records(
            filter_query={
                "name": self.name,
            },
            projection={"quality_control": 1},
        )

        if not records:
            raise ValueError(f"No records found for name: {self.name}")

        self.record = records[0]
        quality_control = self.record.get("quality_control", {})

        print(quality_control)

        self.dataframe = pd.DataFrame(quality_control["metrics"]) if quality_control and "metrics" in quality_control else None

        print(self.dataframe)
