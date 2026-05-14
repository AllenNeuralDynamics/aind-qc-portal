"""Plugin file for custom Panel server endpoints"""

import json
from pathlib import Path

from aind_data_access_api.document_db import MetadataDbClient
from tornado.web import HTTPError, RequestHandler

from aind_qc_portal.view_contents.data_utils import upload_temporary_metadata
from aind_qc_portal.view_contents.panels.media.utils import clean_reference_prefix, get_s3_url

_docdb_client = MetadataDbClient(
    host="api.allenneuraldynamics.org",
    version="v2",
)


class UploadMetadataHandler(RequestHandler):
    """Request handler for uploading metadata"""

    def post(self):
        """Handle POST requests to upload metadata"""
        try:
            # Parse JSON from request body
            if self.request.body:
                metadata = json.loads(self.request.body)
            else:
                metadata = None

            if not metadata:
                raise HTTPError(400, "No metadata provided.")

            upload_temporary_metadata(metadata)
            status_code = 200  # Temporary success status
            self.set_header("Content-Type", "application/json")
            self.write({"status": status_code})
        except json.JSONDecodeError:
            raise HTTPError(400, "Invalid JSON in request body.")
        except Exception as e:
            raise HTTPError(500, f"Failed to upload metadata: {str(e)}")


class GetSignedReferenceHandler(RequestHandler):
    """Request handler for returning a pre-signed S3 URL for a validated metric reference"""

    def set_default_headers(self):
        """Set permissive CORS headers for public access."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, asset_name):
        """Handle CORS preflight requests."""
        self.set_status(204)
        self.finish()

    def get(self, asset_name):
        """Handle GET requests to validate and sign a metric reference"""
        reference = self.get_argument("reference", None)

        if not reference:
            raise HTTPError(400, "Missing required query parameter: reference")

        records = _docdb_client.retrieve_docdb_records(
            filter_query={"name": asset_name},
            projection={"quality_control": 1, "name": 1, "location": 1},
        )

        if not records:
            raise HTTPError(404, f"Asset '{asset_name}' not found.")

        record = records[0]
        quality_control = record.get("quality_control", {})
        metrics = quality_control.get("metrics", [])

        reference_found = any(
            metric.get("reference") == reference
            for metric in metrics
            if metric.get("reference") is not None
        )

        if not reference_found:
            raise HTTPError(403, f"Reference '{reference}' is not associated with any metric in asset '{asset_name}'.")

        if "s3" in reference:
            bucket = reference.split("/")[2]
            key = "/".join(reference.split("/")[3:])
        else:
            location = record.get("location", "")
            if not location.startswith("s3://"):
                raise HTTPError(500, f"Asset location '{location}' is not an s3:// URI.")
            parts = location.split("/")
            bucket = parts[2]
            prefix = "/".join(parts[3:])
            key = str(Path(prefix) / clean_reference_prefix(reference))

        url = get_s3_url(bucket, key)
        if not url:
            raise HTTPError(500, "Failed to generate pre-signed URL.")

        self.set_header("Content-Type", "application/json")
        self.write({"url": url})


ROUTES = [
    ("/upload_metadata", UploadMetadataHandler, {}),
    (r"/get-signed-reference/([^/]+)", GetSignedReferenceHandler, {}),
]

# Export ROUTES for Panel server to discover
__all__ = ["ROUTES"]
