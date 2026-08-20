---
name: zombie-qc-view-contract
description: Maintain the QC Portal HTTP and view-data contracts used by Zombie's QC page and asset-reference links.
---

# Zombie QC view contract

Zombie's `/quality_control` page reads DocDB v2 records and renders the portal's metric model. Preserve the portal behavior that `ViewData` loads pending edits, validates them, and on save appends status history and curation history while replacing ordinary metric values. Zombie derives current status from the latest `status_history`, treats missing status as `Pending`, and aggregates `Fail > Pending > Pass`; changes to history shape or metric validation affect both applications.

The browser upload bridge is POST `/upload_metadata`, which stores transient metadata in `pn.state.metadata`. Reference media uses GET `/get-signed-reference/<asset_name>?reference=...`. The handler must validate that the exact reference exists in the asset's metric list, resolve relative references against the asset's S3 location, and return `{url}` for a pre-signed object. Keep path quoting, missing-reference errors, and the wildcard CORS behavior compatible with the current browser client.

Do not replace the live edit URL or invent a second reference endpoint without updating Zombie's `resolveReference()` flow. Test handler behavior with the existing Panel/test-client patches and test `ViewData` with mocked DocDB, including pending edits, status-history append, curation history, invalid references, and signed-reference failures.
