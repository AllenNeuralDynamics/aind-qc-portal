# QC Portal

The QC Portal app makes the `quality_control` metadata (see [aind-data-schema](https://github.com/allenNeuralDynamics/aind-data-schema)) explorable and provides tools for manual annotation of metrics.

## Portal

## Subject view

## Experiment view

[todo]

## QC view

## Launch

```
panel serve src/aind_qc_portal/qc_portal_app.py src/aind_qc_portal/qc_asset_app.py src/aind_qc_portal/qc_app.py --autoreload --show --port 5007 --allow-websocket-origin=10.128.141.92:5007 --keep-alive 10000
```

(port is set to differentiate from aind-metadata-viz app)
