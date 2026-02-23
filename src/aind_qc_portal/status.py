""""Status check functions for AIND QC Portal."""

import traceback
from aind_qc_portal.view_contents.data import ViewData

def check_load_qc_from_docdb():
    """
    Try loading QC data from DocDB using portal functions for a hardcoded asset.
    Returns: dict with status and error info.
    """
    asset_name = "behavior_711042_2024-08-07_12-20-41"
    try:
        vd = ViewData(asset_name)
        if vd.dataframe is not None and not vd.dataframe.empty:
            return {"status": "success", "num_metrics": len(vd.dataframe), "asset_name": asset_name}
        else:
            return {"status": "error", "error": "No QC metrics found in dataframe", "asset_name": asset_name}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc(), "asset_name": asset_name}

def check_docdb_read_write_roundtrip():
    """
    Test reading and writing a record to DocDB using a dedicated test record.
    Flips a metric value between -1 and 1 on each attempt.
    Returns: dict with status and error info.
    """
    import time
    test_asset_name = "qc_portal_status_test"
    metric_name = "status_test_metric"
    try:
        vd = ViewData(test_asset_name)
        # If record/metric exists, get current value, else create
        record = vd.get_fresh_record() if hasattr(vd, 'get_fresh_record') else vd.record
        qc = record.get("quality_control", {}) if record else {}
        metrics = qc.get("metrics", []) if qc else []
        metric = next((m for m in metrics if m.get("name") == metric_name), None)
        if metric is not None:
            current_value = metric.get("value", -1)
            new_value = 1 if current_value == -1 else -1
            metric["value"] = new_value
        else:
            # Create the metric if it doesn't exist
            metric = {
                "name": metric_name,
                "object_type": "QC metric",
                "value": -1,
                "status_history": [],
                "tags": [],
            }
            metrics.append(metric)
            qc["metrics"] = metrics
            record["quality_control"] = qc
            new_value = -1
        # Upsert the record
        success, msg = vd.submit_changes_to_docdb(record)
        time.sleep(1)  # Give DocDB a moment to update
        # Read back to verify
        vd2 = ViewData(test_asset_name)
        record2 = vd2.get_fresh_record() if hasattr(vd2, 'get_fresh_record') else vd2.record
        qc2 = record2.get("quality_control", {}) if record2 else {}
        metrics2 = qc2.get("metrics", []) if qc2 else []
        metric2 = next((m for m in metrics2 if m.get("name") == metric_name), None)
        if metric2 and metric2.get("value") == new_value:
            return {"status": "success", "asset_name": test_asset_name, "metric": metric_name, "value": new_value}
        else:
            return {"status": "error", "error": "Roundtrip value mismatch", "asset_name": test_asset_name, "metric": metric_name}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

def check_s3_media_access(bucket_name):
    """
    Try reading a media file from S3 bucket (aind-open-data or codeocean).
    Returns: dict with status and error info.
    """
    pass

def check_zombie_squirrel_access():
    """
    Test access to zombie-squirrel service/endpoint.
    Returns: dict with status and error info.
    """
    pass

def run_all_status_checks():
    """
    Run all status checks and return a summary.
    Returns: dict with results for each check.
    """
    results = {
        "docdb_load": check_load_qc_from_docdb(),
        "docdb_roundtrip": check_docdb_read_write_roundtrip(),
        # ...other checks...
    }
    return results
