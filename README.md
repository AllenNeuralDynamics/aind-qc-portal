# QC Portal

The [QC Portal](https://qc.allenneuraldynamics.org/qc_portal_app) is a browser application that allows users to view and interact with the AIND QC metadata and to annotate ``PENDING`` metrics with qualitative evaluations. The portal is currently maintained by Dan Birman in scientific computing, reach out with any questions or concerns.

The portal works by pulling the metadata from the Document Database (DocDB) and pulling reference figures from Code Ocean (CO) data assets, or from storage in Kachery Cloud.

The portal allows users to annotate `PENDING` metrics. Logged in users can modify the value, state, and notes on metrics. When you make changes the **submit** button will be enabled. Submitting pushes your updates to DocDB along with a timestamp and your name.

For general documentation about the QC metadata, go [here](https://aind-data-schema.readthedocs.io/en/latest/quality_control.html).

## Defining metrics for the QC portal

For AIND users, we expect your metrics to have actionable `value` fields. Either the value should be a number that a rule can be applied to (e.g. a threshold) or it should refer to the state of the reference (e.g. "high drift" when linked to a drift map, or "acceptable contrast" when linked to a video).

All metrics should have a `reference` figure attached. Even if you are just calculating numbers, your reference figures can put those numbers in context for viewers.

**Q: How do reference URLs get pulled into the QC Portal?**

Each metric is associated with a reference figure. We support:

- Vector files (svg, pdf)
- Images (png, jpg, etc)
- Videos (mp4)
- Neuroglancer links (url)
- Rerun files (rrd)

Figures, images, and videos can be any size, but they will fit best on the screen if they are landscape and shaped roughly like a computer screen (for example, 1280×800 or 1900×1200 px).

You can link to your references in one of four ways:

- Provide a relative path to a file in the data asset's S3 bucket, i.e. "figures/my_figure.png". The mount/asset name should not be included.
- Provide a url to a publicly accessible file, i.e. "https://mywebsite.com/myfile.png"
- Provide a path to any public S3 bucket, i.e. "s3://bucket/myfile.png"
- Provide a kachery-cloud hash, i.e. "sha1://uuid.ext", note that only for FigURL hashes you **must append the filetype**. The easiest way to do this is to set the `label` field to the filename, see below.

**Q: I saw fancy things like dropdowns in the QC Portal, how do I do that?**

The portal supports a few special cases to allow a bit more flexibility or to constrain the actions that manual annotators can take. Install the [`aind-qcportal-schema`](https://github.com/AllenNeuralDynamics/aind-qcportal-schema/blob/dev/src/aind_qcportal_schema/metric_value.py) package and set the `value` field to the corresponding pydantic object to use these. Current options include:

- Dropdowns (optionally the options can auto-set the value)
- Checkboxes (again options can auto-set the value)
- Rule-based metrics (the rule is automatically run to set the value)
- Multi-asset metrics where each asset is assigned it's own value

There are also some custom rules for the value field. If you provide:

- Two strings separated by a semicolon `;` they will be displayed in a "Swipe" pane that lets you swipe back and forth between the two things. Mostly useful for overlay images.
- A dictionary where every value is a list of equal length, it will be displayed as a table where the keys are column headers and the values are rows. If a key "index" is included the values will be used to name the rows.

## How to upload data from CO Capsules

### Preferred workflow

Use the preferred workflow if you are **generating a data asset**, e.g. when uploading raw data or generating a new derived data asset. Your `quality_control.json` will go in the top level and your figures will go in a folder. Follow the steps below:

1. Develop your QC pipeline, generating metrics and reference figures as needed. Place references in the `results/` folder.
2. Populate your `QCEvaluation` objects with metrics. The `reference` field should contain the path *relative to the results* folder. I.e. the file `results/figures/my_figure.png` should be included as `QCMetric.reference = "figures/my_figure.png"`. 
3. Write the standard QC file: `QualityControl.write_standard_file()`

Make sure to follow the standard instructions for building derived assets: copy all metadata files, upgrade the data_description to derived, and name your asset according to the expected conventions. Make sure to tag your data asset as `derived` so that it will be picked up by the indexer.

Done! In the preferred workflow no additional permissions are required. Your QC data will appear in the portal within four hours of creation.

### Alternate workflow

Use the alternate workflow if you are **not generating a data asset** and therefore need to push your QC data back to an already existing data asset. You will push your `QCEvaluation` objects directly to DocDB and you will need to push your figures to `kachery-cloud`, an external repository that generates permanent links to uploaded files.

Two things need to be setup in your capsule:

1. You'll need to run `pip install kachery-cloud` and `pip install aind-data-access-api[docdb]` as part of your environment setup.
2. In your capsule settings attach the `aind-codeocean-power-user` role. If you don't have access to this role, ask someone in Scientific Computing to attach it for you.

#### (1) Acquire your DocDB _id using your data asset's name

To upload directly to DocDB you'll need to know your asset's `_id`. You can get it by adding this code to your capsule and calling `query_docdb_id(asset_name)`. Note that this *is not the data asset id in Code Ocean*!

```{python}
def query_docdb_id(asset_name: str):
    """
    Returns docdb_id for asset_name.
    Returns empty string if asset is not found.
    """

    # Resolve DocDB id of data asset
    API_GATEWAY_HOST = "api.allenneuraldynamics.org"
    DATABASE = "metadata_index"
    COLLECTION = "data_assets"

    docdb_api_client = MetadataDbClient(
    host=API_GATEWAY_HOST,
    database=DATABASE,
    collection=COLLECTION,
    )

    response = docdb_api_client.retrieve_docdb_records(
    filter_query={"name": asset_name},
    projection={"_id": 1},
    )

    if len(response) == 0:
        return ""
    docdb_id = response[0]["_id"]
    return docdb_id
```

#### (2) Generate your QC data

Generate your metrics and reference figures. Put your figures in folders in the results, e.g. `results/figures/` and store the filepaths.

#### (3) Push figures to `kachery-cloud`

Your figures should already exist in folders in your `results/`. Then, in your capsule code, pull the Kachery Cloud credentials using this function:

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

get_kachery_secrets()
```

The credentials are now stored as enviroment keys.

Each of your figures should then be uploaded using the `store_file` function:

```
import kachery_cloud as kcl

file_path = "your_file_path.ext"
uri = kcl.store_file(file_path, label=file_path)
```

#### (4) Generate your QCEvaluation objects

Generate your `QCEvaluation` objects now. Make sure to set the `QCMetric.reference` field of each metric to the returned uri `QCMetric.reference = uri` for that figure. Each URI is a unique hashed string that will allow the portal to recover your file. Make sure to include the `label` parameter or we won't be able to identify your filetype in the portal.

Store all your `QCEvaluation` objects in a list.

#### (5) Push metadata to DocDB

Run the following code snippet. You can pass all your evaluations as a list or pass them one at a time:

```{python}
session = boto3.Session()
credentials = session.get_credentials()
host = "api.allenneuraldynamics.org"

auth = AWSRequestsAuth(
aws_access_key=credentials.access_key,
aws_secret_access_key=credentials.secret_key,
aws_token=credentials.token,
aws_host="api.allenneuraldynamics.org",
aws_region='us-west-2',
aws_service='execute-api'
)
url = f"https://{host}/v1/add_qc_evaluation"
post_request_content = {"data_asset_id": docdb_id,
                        "qc_evaluation": qc_eval.model_dump(mode='json')}
response = requests.post(url=url, auth=auth, 
                        json=post_request_content)

if response.status_code != 200:
    print(response.status_code)
    print(response.text)
```

If you get errors, contact Dan for help debugging.

### Reference/Figure recommendations

In general, the portal works best with figures that are in landscape view, i.e. shaped like your monitor.

#### Images

We recommend you store rasterized files as PNG and vector files as SVG or PDF.

#### Videos

You can use gifs (<10 MB) or mp4 files (<100 MB). Make sure your mp4 files are *browser-compatible* or they will not work in the portal.

#### Neuroglancer

You can set the reference directly to a neuroglancer link, they will open embedded in the portal and can be easily switched to fullscreen mode.

#### Rerun

Rerun files (.rrd) can be linked in the reference, they will open in the rerun app embedded in the portal and can be easily switched to fullscreen mode.

#### Other

We're prepared to support basically any kind of browser-displayable object. Reach out with ideas.

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