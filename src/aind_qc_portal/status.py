""""Status check functions for AIND QC Portal."""

import traceback
from aind_qc_portal.view_contents.data import ViewData
from zombie_squirrel import unique_project_names, asset_basics
from aind_qc_portal.view_contents.panels.media.utils import get_s3_client

def check_load_qc_from_docdb(asset_name):
    """
    Try loading QC data from DocDB using portal functions for a list of assets.
    Returns: dict with status and error info.
    """
    try:
        vd = ViewData(asset_name)
        if vd.dataframe is not None and not vd.dataframe.empty:
            return {"status": "success", "num_metrics": len(vd.dataframe), "asset_name": asset_name}
        else:
            return {"status": "error", "error": "No QC metrics found in dataframe", "asset_name": asset_name}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "asset_name": asset_name}

def check_s3_media_access(asset_name):
    """
    Try reading a media file from S3 for the given asset.
    Returns: dict with status and error info.
    """
    try:
        vd = ViewData(asset_name)
        bucket = vd.s3_bucket
        prefix = vd.s3_prefix
        if not bucket or not prefix:
            return {"status": "error", "error": "Missing S3 bucket or prefix", "asset_name": asset_name}

        s3 = get_s3_client(bucket)
        # List files in the media directory
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        files = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"].endswith(('.mp4', '.tif', '.png', '.jpg'))]
        if not files:
            return {"status": "error", "error": "No media files found in S3", "asset_name": asset_name}
        file_key = files[0]
        try:
            # Try to read first 10 bytes of the file
            obj = s3.get_object(Bucket=bucket, Key=file_key)
            content = obj["Body"].read(10)
            return {"status": "success", "asset_name": asset_name, "file": file_key}
        except Exception as e:
            return {"status": "error", "error": str(e), "asset_name": asset_name, "file": file_key}
    except Exception as e:
        return {"status": "error", "error": str(e), "asset_name": asset_name}
    
def check_zombie_squirrel_access():
    """
    Test access to zombie-squirrel service/endpoint.
    Returns: dict with status and error info.
    """
    try:
        projects = unique_project_names()
        basics = asset_basics()
        if not isinstance(projects, list):
            return {"status": "error", "error": "unique_project_names did not return a list"}
        if not hasattr(basics, 'shape'):
            return {"status": "error", "error": "asset_basics did not return a dataframe-like object"}
        return {"status": "success", "num_projects": len(projects), "num_assets": getattr(basics, 'shape', (0,))[0]}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def run_all_status_checks():
    """
    Run all status checks and return a summary.
    Returns: dict with results for each check.
    """
    asset_names = [
        "804430_2025-10-30_23-15-07_processed_2026-01-26_22-15-12",
        "multiplane-ophys_827543_2025-12-12_14-09-27_processed_2025-12-13_17-35-45"
    ]
    results = {
        "docdb_load": {},
        "s3_media_access": {},
        "zombie_squirrel": check_zombie_squirrel_access(),
    }
    for asset_name in asset_names:
        results["docdb_load"][asset_name] = check_load_qc_from_docdb(asset_name)
        results["s3_media_access"][asset_name] = check_s3_media_access(asset_name)
    return results