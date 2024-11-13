"""Custom mappings from DocDB -> Dataframe columns for the platform portal"""

from pydantic import BaseModel
from typing import Optional
from aind_qc_portal.projects.smartspim_processing import *
from aind_qc_portal.utils import format_link


class Mapping(BaseModel):
    """Mapping information for a column"""

    docdb_location: str
    processing: Optional[str]
    backup_location: Optional[str]
    backup_processing: Optional[str]


smartspim = {
    "Subject ID": Mapping(
        docdb_location="subject.subject_id",
    ),
    "Genotype": Mapping(
        docdb_location="",
    ),
    "Institution": Mapping(
        docdb_location="",
    ),
    "Acquisition Time": Mapping(
        docdb_location="",
    ),
    "Processed Time": Mapping(
        docdb_location="",
    ),
    "Orientation": Mapping(
        docdb_location="",
    ),
    "Stitched Link": Mapping(
        docdb_location="",
    ),
    "Segmentation Channels": Mapping(
        docdb_location="",
    ),
    "CH1": Mapping(
        docdb_location="",
        processing=format_link,
    ),
    "CH2": Mapping(
        docdb_location="",
    ),
    "CH3": Mapping(
        docdb_location="",
    ),
    "Registration Channel": Mapping(
        docdb_location="",
    ),
    "rCH1": Mapping(
        docdb_location="",
    ),
    "rCH2": Mapping(
        docdb_location="",
    ),
    "rCH3": Mapping(
        docdb_location="",
    ),
    "Data Asset Name": Mapping(
        docdb_location="name",
    ),
}

# asset ID, mouse ID, genotype, session type, acquisition date, processing date, pipeline version
behavior = {}

# {'_id': '901c7e0e-2a7d-4600-aaa2-b4d40330d132', 'acquisition': None, 'created': '2024-05-07T16:39:45Z', 'data_description': None, 'describedBy': 'https://raw.githubusercontent.com/AllenNeuralDynamics/aind-data-schema/main/src/aind_data_schema/core/metadata.py', 'external_links': [{'Code Ocean': '28552d8f-fc1b-4f3f-9a9e-7f89b6a78ae4'}], 'instrument': None, 'last_modified': '2024-06-13T22:28:57.365951', 'location': 's3://codeocean-s3datasetsbucket-eg0euwi4ez6z/28552d8f-fc1b-4f3f-9a9e-7f89b6a78ae4', 'metadata_status': 'Unknown', 'name': 'behavior_655019_2020-10-10_01-00-24_processed_2024-05-07_16-39-45', 'procedures': None, 'processing': None, 'rig': None, 'schema_version': '0.2.7', 'session': None, 'subject': None}
