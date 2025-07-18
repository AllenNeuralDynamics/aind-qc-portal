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
def get_qc_df_from_id(id: str) -> tuple[dict, Optional[pd.DataFrame]]:
    """Get a QualityControl object from the database by its unique identifier.

    Parameters
    ----------
    id : str
        The unique identifier of the QualityControl record.

    Returns
    -------
    Optional[QualityControl]
        The QualityControl object if found, None otherwise.
    """
    records = client.retrieve_docdb_records(
        filter_query={
            "_id": id,
        },
        projection={"quality_control": 1},
    )

    record = records[0]
    quality_control = record.get("quality_control", {})

    df = pd.DataFrame(quality_control["metrics"]) if quality_control and "metrics" in quality_control else None

    return record, df
