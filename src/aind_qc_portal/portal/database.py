"""Database for the Portal app

The database pulls _id information and more complete record information from DocDB
and uses to populate the view for the user. Aggressive caching is used to prevent
updaetes to the database from causing excessive load on the DocDB server and to reduce
page load times for users looking at large numbers of records.
"""

from datetime import datetime
from typing import Optional
from aind_data_access_api.document_db import MetadataDbClient
import panel as pn

client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)

FIELDS = [
    "name",
]

TTL_DAY = 24 * 60 * 60


class Database:
    """Database for the Portal app"""

    def build_query(
        self,
        name_string: Optional[str] = None,
        project_name: Optional[str] = None,
        subject_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Construct a MongoDB query using the available parameters"""

        query = {}

        if name_string:
            query["name"] = {"$regex": name_string, "$options": "i"}

        if project_name:
            query["data_description.project_name"] = project_name

        if subject_id:
            query["subject.subject_id"] = subject_id

        # [TODO] Add date filtering

        return query

    def get_ids(self, query: dict):
        """Get a list of record IDs matching the query"""

        try:
            ids = client.retrieve_docdb_records(
                filter_query=query,
                projection={"_id": 1},
            )
            return ids
        except Exception as e:
            print(f"Error fetching IDs: {e}")
            return []

    def get_records(self, query: dict):
        """Get complete records matching the query"""

        try:
            records = client.retrieve_docdb_records(
                filter_query=query,
                projection={f"{field}": 1 for field in FIELDS},
            )
            return records
        except Exception as e:
            print(f"Error fetching records: {e}")
            return []

    @pn.cache()
    def get_unique_project_names(self):
        """Get unique project names from the database"""

        try:
            unique_projects = client.aggregate_docdb_records(
                pipeline=[
                    {"$group": {"_id": "$data_description.project_name"}},
                    {"$project": {"project_name": "$_id", "_id": 0}}
                ],
            )
            return [project["project_name"] for project in unique_projects]
        except Exception as e:
            print(f"Error fetching unique project names: {e}")
            return []

    @pn.cache()
    def get_subject_ids(self, project_names: list[str]):
        """Get unique subject IDs for the given project names"""

        try:
            subject_ids = client.aggregate_docdb_records(
                pipeline=[
                    {"$match": {"data_description.project_name": {"$in": project_names}}},
                    {"$group": {"_id": "$subject.subject_id"}},
                    {"$project": {"subject_id": "$_id", "_id": 0}}
                ],
            )
            return [subject["subject_id"] for subject in subject_ids]
        except Exception as e:
            print(f"Error fetching subject IDs: {e}")
            return []