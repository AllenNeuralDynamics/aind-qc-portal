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


behavior = {

}