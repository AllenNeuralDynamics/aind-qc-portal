from aind_data_schema.core.quality_control import QualityControl
from aind_data_access_api.document_db import MetadataDbClient
import numpy as np
import panel as pn

# API_GATEWAY_HOST = "api.allenneuraldynamics.org"
# DATABASE = "metadata_index"
# COLLECTION = "data_assets"

API_GATEWAY_HOST = "api.allenneuraldynamics-test.org"
DATABASE = "test"
COLLECTION = "data_assets"

TIMEOUT_1M = 60
TIMEOUT_1H = 60 * 60
TIMEOUT_24H = 60 * 60 * 24

client = MetadataDbClient(
    host=API_GATEWAY_HOST,
    database=DATABASE,
    collection=COLLECTION,
)


def qc_from_id(id: str):
    response = client.retrieve_docdb_records(filter_query={"_id": id}, limit=1)
    return response[0]


def qc_update_to_id(id: str, qc: QualityControl):
    qc.evaluate_status()
    response = client.upsert_one_docdb_record(
        record={"_id": id, "quality_control": qc.dict()}
    )
    if response.status_code != 200:
        print(response.json())


@pn.cache()
def get_name_from_id(id: str):
    response = client.aggregate_docdb_records(
        pipeline=[{"$match": {"_id": id}}, {"$project": {"name": 1, "_id": 0}}]
    )
    return response[0]["name"]


@pn.cache()
def get_subj_from_id(id: str):
    response = client.aggregate_docdb_records(
        pipeline=[{"$match": {"_id": id}}, {"$project": {"subject": 1, "_id": 0}}]
    )
    return response[0]["subject"]["subject_id"]


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
    raw_name = _raw_name_from_derived(asset_name)
    response = client.retrieve_docdb_records(
        filter_query={"name": {"$regex": raw_name, "$options": "i"}}, limit=0
    )
    return response


def get_assets_by_subj(subj: str):
    response = client.retrieve_docdb_records(
        filter_query={"subject.subject_id": subj}, limit=0
    )
    return response


@pn.cache(ttl=TIMEOUT_1H)
def get_meta():
    response = client.aggregate_docdb_records(
        pipeline=[
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "qc_exists": {
                        "$cond": {
                            "if": {
                                "$gt": [
                                    {"$type": "$quality_control"},
                                    "missing",
                                ]
                            },
                            "then": "$quality_control.overall_status",
                            "else": None,
                        }
                    },
                }
            },
            {
                "$group": {
                    "_id": None,
                    "data": {
                        "$push": {
                            "_id": "$_id",
                            "name": "$name",
                            "qc_exists": "$qc_exists",
                        }
                    },
                }
            },
            {"$project": {"_id": 0, "data": 1}},
        ]
    )
    return response[0]["data"]


@pn.cache(ttl=TIMEOUT_24H)  # twenty-four hour cache
def get_all():
    filter = {}
    limit = 50
    paginate_batch_size = 500
    response = client.retrieve_docdb_records(
        filter_query=filter,
        limit=limit,
        paginate_batch_size=paginate_batch_size,
    )

    return response


@pn.cache
def get_subjects():
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
    """Get the raw JSON sessions list for a subject

    Parameters
    ----------
    subject_id : string or int
        _description_

    Returns
    -------
    _type_
        _description_
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
