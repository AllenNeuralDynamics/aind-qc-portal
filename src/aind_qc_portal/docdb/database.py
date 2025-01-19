import os
from typing import Optional

import numpy as np
import panel as pn
from aind_data_access_api.document_db import MetadataDbClient
from aind_data_schema.core.quality_control import QualityControl
from aind_data_access_api.helpers.docdb import get_projection_by_id

API_GATEWAY_HOST = os.getenv(
    "API_GATEWAY_HOST", "api.allenneuraldynamics-test.org"
)
DATABASE = os.getenv("DATABASE", "metadata_index")
COLLECTION = os.getenv("COLLECTION", "data_assets")

TIMEOUT_1M = 60
TIMEOUT_1H = 60 * 60
TIMEOUT_24H = 60 * 60 * 24

client = MetadataDbClient(
    host=API_GATEWAY_HOST,
    database=DATABASE,
    collection=COLLECTION,
)


@pn.cache()
def get_project_names():
    """Get all unique project names from the database.

    Returns
    -------
    list[str]
        List of unique project names found in the database.
    """
    response = client.aggregate_docdb_records(
        pipeline=[
            {"$group": {"_id": "$data_description.project_name"}},
            {
                "$group": {
                    "_id": None,
                    "unique_project_names": {"$push": "$_id"},
                }
            },
            {"$project": {"_id": 0, "unique_project_names": 1}},
        ]
    )
    return response[0]["unique_project_names"]


def record_from_id(id: str) -> dict | None:
    """Get the complete record from the database for a given ID.

    Parameters
    ----------
    id : str
        The unique identifier of the record.

    Returns
    -------
    dict | None
        The complete record as a dictionary if found, None otherwise.
    """
    response = client.retrieve_docdb_records(filter_query={"_id": id}, limit=1)
    if len(response) == 0:
        return None
    return response[0]


def project_name_from_id(id: str) -> Optional[str]:
    """Get the project name from the database for a given ID.

    Parameters
    ----------
    id : str
        The unique identifier of the record.

    Returns
    -------
    Optional[str]
        The project name if found, None otherwise.
    """

    response = client.retrieve_docdb_records(
        filter_query={"_id": id},
        projection={"data_description.project_name": 1},
        limit=1,
    )
    if len(response) == 0:
        return None
    return response[0].get("data_description", {}).get("project_name")


def qc_update_to_id(id: str, qc: QualityControl):
    """Update or insert quality control information for a given record ID.

    Parameters
    ----------
    id : str
        The unique identifier of the record to update.
    qc : QualityControl
        The quality control object containing the update information.

    Returns
    -------
    dict
        Response from the database update operation.
    """
    print("Uploading QC")
    print(qc.model_dump())
    response = client.upsert_one_docdb_record(
        record={"_id": id, "quality_control": qc.model_dump()}
    )
    return response


@pn.cache()
def get_name_from_id(id: str):
    """Get the name field from a record with the given ID.

    Parameters
    ----------
    id : str
        The unique identifier of the record.

    Returns
    -------
    str
        The name field from the record.
    """
    response = client.aggregate_docdb_records(
        pipeline=[{"$match": {"_id": id}}, {"$project": {"name": 1, "_id": 0}}]
    )
    return response[0]["name"]


@pn.cache()
def get_subj_from_id(id: str):
    """Get the subject ID from a record with the given ID.

    Parameters
    ----------
    id : str
        The unique identifier of the record.

    Returns
    -------
    str | None
        The subject ID if found, None otherwise.
    """
    response = get_projection_by_id(
        client=client, _id=id, projection={"subject.subject_id": 1}
    )
    if response is not None:
        return response["subject"]["subject_id"]
    return None


@pn.cache()
def _raw_name_from_derived(s):
    """Returns just the raw asset name from an asset that is derived, i.e. has >= 4 underscores

    Parameters
    ----------
    s : str
        Raw or derived asset name

    Returns
    -------
    str
        Raw asset name, split off from full name
    """
    if s.count("_") >= 4:
        parts = s.split("_", 4)
        return "_".join(parts[:4])
    return s


@pn.cache(ttl=TIMEOUT_1H)
def get_assets_by_name(asset_name: str):
    """Get all assets that match a given asset name pattern.

    Parameters
    ----------
    asset_name : str
        The asset name to search for (will be converted to raw name if derived).

    Returns
    -------
    list[dict]
        List of matching asset records.
    """
    raw_name = _raw_name_from_derived(asset_name)
    response = client.retrieve_docdb_records(
        filter_query={"name": {"$regex": raw_name, "$options": "i"}}, limit=0
    )
    return response


def get_assets_by_subj(subj: str):
    """Get all assets associated with a given subject ID.

    Parameters
    ----------
    subj : str
        The subject ID to search for.

    Returns
    -------
    list[dict]
        List of asset records associated with the subject.
    """
    response = client.retrieve_docdb_records(
        filter_query={"subject.subject_id": subj}, limit=0
    )
    return response


def get_meta():
    """Get metadata information for all records.

    Returns
    -------
    list[dict]
        List of records containing ID, name, and quality control information.
    """
    response = client.aggregate_docdb_records(
        pipeline=[
            {"$project": {"_id": 1, "name": 1, "quality_control": 1}},
        ]
    )
    return response


@pn.cache(ttl=TIMEOUT_24H)  # twenty-four hour cache
def get_all():
    """Get a limited set of all records from the database.

    Returns
    -------
    list[dict]
        List of records, limited to 50 entries.
    """
    filter = {}
    limit = 50
    paginate_batch_size = 500
    response = client.retrieve_docdb_records(
        filter_query=filter,
        limit=limit,
        paginate_batch_size=paginate_batch_size,
    )

    return response


@pn.cache(ttl=TIMEOUT_1H)
def get_project_data(project_name: str):
    """Get detailed data for all records associated with a specific project.

    Parameters
    ----------
    project_name : str
        The name of the project to query.

    Returns
    -------
    list[dict]
        List of records containing detailed information about the project's assets.
    """
    filter = {"data_description.project_name": project_name}
    limit = 0
    paginate_batch_size = 500
    response = client.retrieve_docdb_records(
        filter_query=filter,
        projection={
            "_id": 1,
            "name": 1,
            "location": 1,
            "subject.subject_id": 1,
            "subject.genotype": 1,
            "session.session_type": 1,
            "session.session_start_time": 1,
            "acquisition.session_type": 1,
            "acquisition.session_start_time": 1,
            "data_description.data_level": 1,
            "data_description.project_name": 1,
            "rig.rig_id": 1,
            "session.experimenter_full_name": 1,
            "quality_control": 1,
        },
        limit=limit,
        paginate_batch_size=paginate_batch_size,
    )

    print(f"Found {len(response)} records for project {project_name}")
    return response


@pn.cache
def get_subjects():
    """Get a list of all unique subject IDs from the database.

    Returns
    -------
    list[int]
        List of unique subject IDs.
    """
    filter = {
        "subject.subject_id": {"$exists": True},
        "session": {"$ne": None},
    }
    limit = 1000
    paginate_batch_size = 100
    response = client.retrieve_docdb_records(
        filter_query=filter,
        projection={"_id": 0, "subject.subject_id": 1},
        limit=limit,
        paginate_batch_size=paginate_batch_size,
    )

    # turn this into a list instead of a nested list
    subjects = []
    for data in response:
        subjects.append(np.int32(data["subject"]["subject_id"]))

    return np.unique(subjects).tolist()


@pn.cache
def get_sessions(subject_id):
    """Get all session information for a given subject.

    Parameters
    ----------
    subject_id : str or int
        The ID of the subject to query sessions for.

    Returns
    -------
    list[dict]
        List of session records for the subject.
    """
    filter = {
        "subject.subject_id": str(subject_id),
        "session": {"$ne": "null"},
    }
    response = client.retrieve_docdb_records(
        filter_query=filter, projection={"_id": 0, "session": 1}
    )

    sessions = []
    for data in response:
        sessions.append(data["session"])

    return sessions
