# QC Portal

The QC Portal app makes the `quality_control` metadata (see [aind-data-schema](https://github.com/allenNeuralDynamics/aind-data-schema)) explorable and provides tools for manual annotation of metrics.

## Portal

## Subject view

## Experiment view

[todo]

## QC view

## Launch

```sh
panel serve src/aind_qc_portal/qc_portal_app.py src/aind_qc_portal/qc_asset_app.py src/aind_qc_portal/qc_app.py --static-dirs images=src/aind_qc_portal/images --autoreload --show --port 5007 --allow-websocket-origin=10.128.141.92:5007 --keep-alive 10000
```

(port is set to differentiate from aind-metadata-viz app)


## CI/CD
There is a `Dockerfile` which includes the entrypoint to launch the app.

### Local dev
1. Build the Docker image locally and run a Docker container:
```sh
docker build -t aind-qc-portal .
docker run -e ALLOW_WEBSOCKET_ORIGIN=localhost:8000 -p 8000:8000 aind-qc-portal
```
2. Navigate to 'localhost:8000` to view the app.