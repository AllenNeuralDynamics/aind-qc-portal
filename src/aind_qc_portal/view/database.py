"""Database for the QC view application."""

from typing import Optional

import panel as pn
import pandas as pd

from aind_data_access_api.document_db import MetadataDbClient

TIMEOUT_1M = 60
TIMEOUT_1H = 60 * 60
TIMEOUT_24H = 60 * 60 * 24

client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)


@pn.cache(max_items=1000, policy="LFU")
def get_qc_df_from_name(name: str) -> tuple[dict, Optional[pd.DataFrame]]:
    """Get a QualityControl object from the database by its name.

    Parameters
    ----------
    name : str
        The name field of the record.

    Returns
    -------
    Optional[QualityControl]
        The QualityControl object if found, None otherwise.
    """
    records = client.retrieve_docdb_records(
        filter_query={
            "name": name,
        },
        projection={"quality_control": 1},
    )

    record = records[0]
    quality_control = record.get("quality_control", {})

    df = pd.DataFrame(quality_control["metrics"]) if quality_control and "metrics" in quality_control else None

    return record, df
