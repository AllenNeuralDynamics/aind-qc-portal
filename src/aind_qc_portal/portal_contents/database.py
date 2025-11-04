"""Database for the Portal app

The database pulls _id information and more complete record information from DocDB
and uses to populate the view for the user. Aggressive caching is used to prevent
updates to the database from causing excessive load on the DocDB server and to reduce
page load times for users looking at large numbers of records.
"""

from datetime import datetime
from typing import Optional
from aind_data_access_api.document_db import MetadataDbClient
import panel as pn
from zombie_squirrel import unique_project_names, asset_basics

client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)

FIELDS = [
    "name",
    "data_description.data_level",
    "data_description.source_data",
    "data_description.modalities",
    "acquisition.acquisition_start_time",
    "subject.subject_id",
    "data_description.project_name",
    "quality_control.status",
    "processing.data_processes.start_date_time",
    "subject.subject_details.genotype",
    "location",
]

TTL_DAY = 24 * 60 * 60
TTL_HOUR = 60 * 60


class Database:
    """Database for the Portal app"""

    def build_query(
        self,
        project_name: Optional[list[str]] = None,
        subject_id: Optional[list[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Construct a MongoDB query using the available parameters"""

        query = {}
        if project_name:
            query["data_description.project_name"] = {"$in": project_name}
        if subject_id:
            query["subject.subject_id"] = {"$in": subject_id}
        if query and (start_date or end_date):
            time_query = {}
            if start_date:
                time_query["$gte"] = start_date.isoformat()
            if end_date:
                time_query["$lte"] = end_date.isoformat()
            query["acquisition.acquisition_start_time"] = time_query

        return query

    def get_query_count(
        self,
        project_name: Optional[list[str]] = None,
        subject_id: Optional[list[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get the count of records matching the query using the zombie-squirrel asset basics df"""

        df = asset_basics()

        # Apply filters
        if project_name:
            df = df[df["project_name"].isin(project_name)]
        if subject_id:
            df = df[df["subject_id"].isin(subject_id)]
        if start_date:
            df = df[df["acquisition_start_time"] >= start_date.isoformat()]
        if end_date:
            df = df[df["acquisition_start_time"] <= end_date.isoformat()]

        return len(df)

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

    def get_unique_project_names(self):
        """Get unique project names from the database"""

        return unique_project_names()

    @pn.cache(ttl=TTL_DAY)
    def get_subject_ids(self, project_names: Optional[list[str]] = None):
        """Get unique subject IDs for the given project names"""

        df = asset_basics()

        # Filter by project_names if provided
        if project_names:
            df = df[df["project_name"].isin(project_names)]

        return df["subject_id"].unique().tolist()

    @pn.cache(ttl=TTL_HOUR)
    def get_acquisition_time_range(self, project_names: list[str]):
        """Get the earliest start time for the given project names"""

        df = asset_basics()

        # Filter by project_names if provided
        if project_names:
            df = df[df["project_name"].isin(project_names)]

        # Get all acquisition_start_time and end_time values, compute min start and max end
        if df.empty:
            return None

        min_start_time = df["acquisition_start_time"].dropna().min()
        max_start_time = df["acquisition_start_time"].dropna().max()

        return (min_start_time, max_start_time)
