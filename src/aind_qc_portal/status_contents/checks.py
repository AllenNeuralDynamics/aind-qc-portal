"""Database and business logic for status checks in AIND QC Portal."""

import traceback

from zombie_squirrel import asset_basics, unique_project_names

from aind_qc_portal.view_contents.data import ViewData
from aind_qc_portal.view_contents.panels.media.utils import get_s3_client


def check_load_qc_from_docdb(asset_names):
    """
    Try loading QC data from DocDB for a list of assets.
    Returns: dict with status and error info for each asset.
    """
    results = {}
    for asset_name in asset_names:
        try:
            vd = ViewData(asset_name)
            if vd.dataframe is not None and not vd.dataframe.empty:
                results[asset_name] = {"status": "success", "num_metrics": len(vd.dataframe), "asset_name": asset_name}
            else:
                results[asset_name] = {
                    "status": "error",
                    "error": "No QC metrics found in dataframe",
                    "asset_name": asset_name,
                }
        except Exception as e:
            results[asset_name] = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "asset_name": asset_name,
            }
    return results


def check_s3_media_access(asset_names):
    """
    Try reading a media file from S3 for a list of assets.
    Returns: dict with status and error info for each asset.
    """
    results = {}
    for asset_name in asset_names:
        try:
            vd = ViewData(asset_name)
            bucket = vd.s3_bucket
            prefix = vd.s3_prefix
            if not bucket or not prefix:
                results[asset_name] = {
                    "status": "error",
                    "error": "Missing S3 bucket or prefix",
                    "asset_name": asset_name,
                }
                continue

            s3 = get_s3_client(bucket)
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            files = [
                obj["Key"]
                for obj in response.get("Contents", [])
                if obj["Key"].endswith((".mp4", ".tif", ".png", ".jpg"))
            ]
            if not files:
                results[asset_name] = {
                    "status": "error",
                    "error": "No media files found in S3",
                    "asset_name": asset_name,
                }
                continue
            file_key = files[0]
            try:
                obj = s3.get_object(Bucket=bucket, Key=file_key)
                _ = obj["Body"].read(10)
                results[asset_name] = {"status": "success", "asset_name": asset_name, "file": file_key}
            except Exception as e:
                results[asset_name] = {"status": "error", "error": str(e), "asset_name": asset_name, "file": file_key}
        except Exception as e:
            results[asset_name] = {"status": "error", "error": str(e), "asset_name": asset_name}
    return results


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
        if not hasattr(basics, "shape"):
            return {"status": "error", "error": "asset_basics did not return a dataframe-like object"}
        return {"status": "success", "num_projects": len(projects), "num_assets": getattr(basics, "shape", (0,))[0]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_all_status_checks():
    """
    Run all status checks and return a summary.
    Returns: dict with results for each check.
    """
    asset_names = [
        "804430_2025-10-30_23-15-07_processed_2026-01-26_22-15-12",
        "multiplane-ophys_827543_2025-12-12_14-09-27_processed_2025-12-13_17-35-45",
    ]
    results = {
        "docdb_load": check_load_qc_from_docdb(asset_names),
        "s3_media_access": check_s3_media_access(asset_names),
        "zombie_squirrel": check_zombie_squirrel_access(),
    }
    return results
