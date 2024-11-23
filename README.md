# QC Portal

The QC Portal app makes the `quality_control` metadata (see [aind-data-schema](https://github.com/allenNeuralDynamics/aind-data-schema)) explorable and provides tools for manual annotation of metrics.

## Uploading data from CO Capsules

### Preferred workflow

Use the preferred workflow if you are generating a data asset. Your `quality_control.json` will go in the top level and your figures will go in a folder. Follow the steps below:

1. Develop your QC pipeline, generating metrics and reference figures as needed. Place references in the `results/` folder.
2. Populate your `QCEvaluation` objects with metrics. The `reference` field should contain the path *relative to the results* folder. I.e. the file `results/figures/my_figure.png` should be included as `QCMetric.reference = "figures/my_figure.png"`. 
3. Write the standard QC file: `QualityControl.write_standard_file()`

Done!

### Alternate workflow

Use the alternate workflow if you are **not** generating a data asset. You need to push your `QCEvaluation` objects to DocDB and you need to push your figures to `kachery-cloud`. 

#### Metadata

#### Figures

You'll need to `pip install kachery-cloud` as part of your environment setup.

Then, in your capsule settings attach the `aind-codeocean-power-user` role. If you don't have access to this role, ask someone in Scientific Computing for help.

In your capsule, pull the Kachery Cloud credentials using this function:

```
def get_kachery_secrets():
    """Obtains the three kachery-cloud environment keys/secrets```
    secret_name = "/aind/prod/kachery/credentials"
    region_name = "us-west-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response['SecretString']
    
    kachery_secrets = json.loads(secret)

    os.environ['KACHERY_ZONE'] = kachery_secrets['KACHERY_ZONE']
    os.environ['KACHERY_CLOUD_CLIENT_ID'] = kachery_secrets['KACHERY_CLOUD_CLIENT_ID']
    os.environ['KACHERY_CLOUD_PRIVATE_KEY'] = kachery_secrets['KACHERY_CLOUD_PRIVATE_KEY']
```

Each of your figures should be uploaded as a stored file:

```
import kachery_cloud as kcl

file_path = "your_file_path.ext"
uri = kcl.store_file(file_path, label=file_path)

QCMetric.reference = uri
```

The URI is a unique hash code that will allow the portal to recover your file. Make sure to include the `label` parameter or we won't be able to identify your filetype in the portal.

### Reference/Figure recommendations

In general, the portal works best with figures that are in landscape view, i.e. shaped like your monitor.

#### Images

We recommend you store rasterized files as PNG and vector files as SVG or PDF.

#### Videos

You can use gifs (<10 MB) or mp4 files (<100 MB). Make sure your mp4 files are *browser-compatible* or they will not work in the portal.

#### Neuroglancer

You can set the reference directly to a neuroglancer link, they will open embedded in the portal in a way that can be easily changed to fullscreen.

#### Rerun

Rerun files (.rrd) can be linked in the reference, they will open in the rerun app embedded in the portal.

## Development

### Launch

```sh
panel serve src/aind_qc_portal/qc_portal_app.py src/aind_qc_portal/qc_asset_app.py src/aind_qc_portal/qc_app.py --static-dirs images=src/aind_qc_portal/images --autoreload --show --port 5007 --allow-websocket-origin=10.128.141.92:5007 --keep-alive 10000
```

(port is set to differentiate from aind-metadata-viz app)


### CI/CD
There is a `Dockerfile` which includes the entrypoint to launch the app.

#### Local dev
1. Build the Docker image locally and run a Docker container:
```sh
docker build -t aind-qc-portal .
docker run -e ALLOW_WEBSOCKET_ORIGIN=localhost:8000 -p 8000:8000 aind-qc-portal
```
2. Navigate to 'localhost:8000` to view the app.

#### AWS
1. On pushes to the `dev` or `main` branch, a GitHub Action will run to publish a Docker image to `ghcr.io/allenneuraldynamics/aind-qc-portal:dev` or `ghcr.io/allenneuraldynamics/aind-qc-portal:latest`.
2. The image can be used by a ECS Service in AWS to run a task container. Application Load Balancer can be used to serve the container from ECS. Please note that the task must be configured with the correct env variables (e.g. `API_GATEWAY_HOST`, `ALLOW_WEBSOCKET_ORIGIN`).