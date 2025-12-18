# This file downloads the QC json from the DocDB client
# Replaces the tags for the metrics with the new dictionary system
# And then re-uploads to the V2 portal

from aind_data_access_api.document_db import MetadataDbClient
import json
import re


client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)

name = "multiplane-ophys_827543_2025-12-12_14-09-27_processed_2025-12-13_17-35-45"

records = client.retrieve_docdb_records(filter_query={"name": name})

record = records[0]

with open("scripts/replace_qc_tags/qc_original.json", "w") as f:
    f.write(json.dumps(record["quality_control"], indent=2))

qc = record["quality_control"]


def transform_tags(metric):
    old_tags = metric.get("tags", [])
    if not old_tags or len(old_tags) == 0:
        return {}

    tag_str = old_tags[0]
    new_tags = {}

    if "Op." in tag_str:
        new_tags["operational"] = "true"
        tag_str = tag_str.replace("Op. ", "")
    else:
        new_tags["operational"] = "false"

    new_tags["type"] = tag_str

    match = re.search(r"VISp_\d+", metric.get("name", ""))
    if match:
        new_tags["fov"] = match.group(0)

    return new_tags


for metric in qc.get("metrics", []):
    metric["tags"] = transform_tags(metric)

qc["default_grouping"] = [("operational",), ("type",), ("fov",)]

with open("scripts/replace_qc_tags/qc.json", "w") as f:
    f.write(json.dumps(qc, indent=2))

record["quality_control"] = qc

client.upsert_one_docdb_record(
    record=record,
)
