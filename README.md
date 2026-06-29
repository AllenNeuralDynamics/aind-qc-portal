# QC Portal

The [QC Portal](https://qc.allenneuraldynamics.org/) is a browser application to view and interact with the AIND QC metadata and to annotate ``PENDING`` metrics with qualitative evaluations. The portal is currently maintained by Dan Birman in scientific computing, reach out with any questions or concerns.

The portal works by pulling the metadata from the Document Database (DocDB) and pulling reference figures from Code Ocean (CO) data assets.

The portal allows users to annotate `PENDING` metrics. Logged in users can modify the value, state, and notes on metrics. When you make changes the **review** button will be enabled. Reviewing and submitting pushes your updates to DocDB along with a timestamp and your name.

[General documentation about the QC metadata](https://aind-data-schema.readthedocs.io/en/latest/quality_control.html).

**IMPORTANT:** The QC Portal relies on certain fields in the metadata being set correctly. These include all files in the `data_description` file. You *must* generate valid metadata or the QC portal will mangle displaying your data assets.

## Metric or Curation?

At AIND we separate our quality control process into two steps:

1. Quality control of each modality in a data asset, i.e. we answer the question: "Can the data in this asset be used for analysis?"
2. Curation of the individual parts of an asset, i.e. we answer the question: "Can each neuron in this data asset be used for analysis?"

`QCMetric` is designed to store information about the former, while the `CurationMetric` should be used for the latter.

## Defining metrics for the QC portal

Metrics should have actionable `value` fields. Either the value should be a number that a rule can be applied to (e.g. a threshold) or it should refer to the state of the reference (e.g. "high drift" when linked to a drift map, or "acceptable contrast" when linked to a video).

Almost all metrics should have a `reference` image, figure, or video attached. Often the `reference` should be shared across multiple metrics. Even if you are just calculating numbers, your reference figures can put those numbers in context for viewers, keep in mind that the portal is a public-facing resource! References can also embed linked pages in an iframe. Embedded links can point to Neuroglancer, FigURL, Rerun, and SortingView.

**Q: How should I organize my hierarchy of metrics?**

To create the hierarchy visible in the QC portal you control the `QualityControl.default_grouping` which sets how tags are split in the tree and the `QCMetric.tags` dictionaries. Note that for multi-modal QC the portal automatically splits by modality at the first level.

A typical metric should have a tag that looks like:

```
tags={
   "probe": "probeA",
   "type": "motion correction"
}
```

And then the `default_grouping = ["probe", "type"]. Note that `"stage"` is always available as a tag for all metrics.

There is no point to using a tag if it isn't shared across more than one metric. The example above will create a hierarchy that is split first into different probes and then the groups of metrics according to their type. If a second data asset is merged with this one that uses a different modality then the portal will split the entire hierarchy by modality at the top level. 

**Q: `QCMetric.value` has type `Any`, what types are acceptable?**

We expect the value to refer to a quantitative or qualitative assessment of some property of the data. When compared to a rule or threshold, the value establishes where that metric passes or fails quality control. So in general, the `value` field should be a number, string, or list of numbers/strings. Below is a table describing how different types are displayed in the portal:

| Type      | Display format | Panel type | Notes |
|---------------|---------------|---------------|---------------|
| Number | Editable number field | [IntInput](https://panel.holoviz.org/reference/widgets/IntInput.html) or [FloatInput](https://panel.holoviz.org/reference/widgets/FloatInput.html) | |
| String | Editable text field | [TextInput](https://panel.holoviz.org/reference/widgets/TextInput.html) | |
| Boolean | Checkbox | [Checkbox](https://panel.holoviz.org/reference/widgets/Checkbox.html) | |
| Dictionary | Table | [Dataframe](https://panel.holoviz.org/reference/panes/DataFrame.html) | Values must have the same length. Use key "index" (case-insensitive) to set custom row labels |
| DropdownMetric | Dropdown | [Dropdown](https://panel.holoviz.org/reference/widgets/Select.html) | See [aind-qcportal-schema](https://github.com/AllenNeuralDynamics/aind-qcportal-schema) |
| CheckboxMetric | Checkboxes | [Checkbox](https://panel.holoviz.org/reference/widgets/Checkbox.html) | See [aind-qcportal-schema](https://github.com/AllenNeuralDynamics/aind-qcportal-schema) |
| CurationMetric | Custom view | | See [aind-qcportal-schema](https://github.com/AllenNeuralDynamics/aind-qcportal-schema) |

**Q: `CurationMetric.value` has type `Any`, what types are acceptable?**

In general you should put a dictionary mapping from an identifier (neuron ID, for example) to the properties of that object. Work with Dan to develop a custom Panel for your curation. The properties you provide can be used to display anything you want in your Panel app, but often you'll want a reference for every object so that you can flip through the images.

Note that in most situations a `CurationMetric` should always be set to pass.

**Q: How does the `reference` get pulled into the QC Portal?**

There are two aspects to references: (1) the type of the reference data, and (2) where the data is stored. These are independent.

*Reference data types*

- Vector files (svg, pdf)
- Images (png, jpg, etc)
- Interactive figures (e.g. altair)
- Videos (mp4)
- Embedded Neuroglancer and Figurl views (url, will be embedded in an *iframe*)
- Rerun files (rrd - version number must be embedded in the filename in the format `filename_vX.Y.Z.rrd`)

*Data storage*

You have a few options for where to store files. In general we *prefer* that you store files in the same data asset where the `quality_control.json` is located. The options below are in order of preference:

1. Provide the path to a file *relative to the `quality_control.json` file*, i.e. "figures/my_figure.png". Do not include the mount, asset name, or s3:// prefix.
2. Provide a kachery-cloud hash, i.e. "sha1://uuid.ext", note that you **must append the filetype**. The easiest way to do this is to set the `label` field to the filename, see below.
3. Provide a url to a publicly accessible file, i.e. "https://mywebsite.com/myfile.png"
4. Provide a path to any public S3 bucket, i.e. "s3://bucket/myfile.png"

Neuroglancer, Figurl, and SortingView links should point to the exact URL that opens the view you want.

**Q: How does the `description` field get parsed?**

The description field gets parsed as markdown. For links use the format `[text](url)`. For mathematical typesetting use [mathjax](https://docs.mathjax.org/en/latest/) styling.

**Q: I saw fancy things like dropdowns in the QC Portal, how do I do that?**

*Custom value fields*

The portal supports a few special cases to allow a bit more flexibility or to constrain the actions that manual annotators can take. Install the [`aind-qcportal-schema`](https://github.com/AllenNeuralDynamics/aind-qcportal-schema/blob/dev/src/aind_qcportal_schema/metric_value.py) package and set the `value` field to the corresponding pydantic object to use these. Current options include:

- Dropdowns (optionally the options can auto-set the value)
- Checkboxes (again options can auto-set the value)
- Rule-based metrics (the rule is automatically run to set the value)
- Multi-asset metrics where each asset is assigned it's own value
- A dictionary where every value is a list of equal length, it will be displayed as a table where the keys are column headers and the values are rows. If a key "index" (case-insensitive: "index", "Index", "INDEX") is included, its values will be used as the row labels instead of appearing as a separate column.

  Example:
  ```python
  # Without index - shows default numeric row indices (0, 1, 2)
  {"channel": ["R", "G", "B"], "value": [0.5, 0.8, 0.3]}
  
  # With index - uses custom row labels (R, G, B)
  {"index": ["R", "G", "B"], "value": [0.5, 0.8, 0.3]}
  ```

*Special reference conditions*

- If you put two reference strings separated by a semicolon `;` they will be displayed in a [Swipe](https://panel.holoviz.org/reference/layouts/Swipe.html) pane that lets you swipe back and forth between the two things. Mostly useful for overlay images.
- If you re-use the same reference in multiple metrics, all of the metrics will be stacked in a single "Metric group".

## Testing Metadata

You can upload *test* metadata to the `/upload_metadata` endpoint and then view them at `/view?name=<metadata.name>`. Uploaded metadata should be a dictionary with the fields the fields `_id`, `name`, `location`, `data_description.project_name` and `quality_control`. This metadata JSON does need to be fully valid, but the `quality_control` object does need to be valid against the current release of [aind-data-schema](https://github.com/AllenNeuralDynamics/aind-data-schema).

```{py}
import json
import requests

with open('metadata.json', 'r') as f:
    metadata = json.load(f)

response = requests.post('https://qc.allenneuraldynamics.org/upload_metadata', json=metadata)
print(f"Status: {response.status_code}")
```

Test metadata is transient, there is no guarantee for how long your metadata will be accessible. In addition, records in DocDB with identical names are prioritized over test records.

## How to upload data from CO Capsules

### Preferred workflow

Use the preferred workflow if you are **generating a data asset**, e.g. when uploading raw data or generating a new derived data asset. Your `quality_control.json` will go in the top level folder alongside other metadata and your figures will go in a subfolder. Follow the steps below:

1. Develop your QC pipeline, generating metrics and reference figures as needed. Place reference files in the `results/` folder.
2. Populate `QCEvaluation` objects with metrics. The `reference` field should contain the path *relative to the results* folder. I.e. the file `results/figures/my_figure.png` should be included as `QCMetric.reference = "figures/my_figure.png"`. 
3. If your input data asset already has a `quality_control.json` file, then load the previous QC file by using `qc = QualityControl(**json.loads(your_file))` and append your evaluations to `qc.evaluations`. If your input data asset has no QC, or this will be a new raw data asset, generate the QC object now `qc = QualityControl(evaluations)`
4. Write the standard QC file to the results folder: `qc.write_standard_file()`

Make sure to follow the standard instructions for [creating derived assets](https://docs.allenneuraldynamics.org/en/latest/data_analysis.html#creating-derived-assets).

Done! In the preferred workflow no additional permissions are required. Your QC data will appear in the portal once they are picked up by the indexer.

## Development

Panel launches the `view` app. The entrypoints for `view.py` are minimal startup files, the actual contents of each app are stored in the *_contents folders.

`panel.py` - the actual QCPanel and Portal classes that aggregate all the different Panels into a user interface
`data/database.py` - a class to handle interacting with DocDB 
`settings.py` - a global Settings class that can be imported into other files to keep track of settings within each app.

All classes used in the UI inherit from `panel.custom.PyComponent` which makes them `Parameterized`, i.e. they can define parameter variables and these can be watched using `object.param.watch(callback, [<param_name>])`. This is what makes the user interface update when data changes in the background.

### Environment Variables

The following environment variables are used by the QC Portal:

#### Required for Local Development

| Variable | Description | Example Value | Notes |
|----------|-------------|---------------|-------|
| `BYPASS_CODEOCEAN_S3` | Bypasses Code Ocean cross-account S3 access | `1` | **Required for local dev** unless you have the `AindCodeOceanBucketCrossAccountAccess` IAM role. Set to `1` to skip role assumption. |
| `AWS_PROFILE` | AWS credentials profile to use | `dev` or `prod` | Required for accessing S3 media files in aind-open-data and the private codeocean buckets. AIND dev credentials will not work on the development branch for testing assets that have media in private buckets. |

#### Required for Panel Server (Docker & Production)

| Variable | Description | Example Value | Notes |
|----------|-------------|---------------|-------|
| `ALLOW_WEBSOCKET_ORIGIN` | WebSocket origins allowed to connect | `localhost:5007` (local)<br>`qc.allenneuraldynamics.org` (prod) | Prevents WebSocket connection errors. For local dev use `localhost:<port>`. |
| `OAUTH_REDIRECT` | OAuth callback URL | `http://localhost:5007` (local)<br>`https://qc.allenneuraldynamics.org` (prod) | Where OAuth provider redirects after authentication. Must match your OAuth app configuration. |

#### Optional - OAuth Authentication

Leave these unset to run in "guest" mode (read-only access):

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `PANEL_OAUTH_PROVIDER` | OAuth provider name | `azure` |
| `PANEL_OAUTH_KEY` | OAuth application client ID | `<your-client-id>` |
| `PANEL_OAUTH_SECRET` | OAuth application client secret | `<your-client-secret>` |
| `PANEL_OAUTH_EXTRA_PARAMS[tenant_id]` | Azure AD tenant ID (Azure only) | `<your-tenant-id>` |
| `PANEL_COOKIE_SECRET` | Secret for cookie encryption | `<your-cookie-secret>` |
| `PANEL_OAUTH_ENCRYPTION` | OAuth token encryption key | `<your-encryption-key>` |

**Setting OAuth variables (bash/zsh):**
```bash
export PANEL_OAUTH_PROVIDER="azure" 
export PANEL_OAUTH_KEY="<your-client-id>"
export PANEL_OAUTH_SECRET="<your-client-secret>"
typeset -A PANEL_OAUTH_EXTRA_PARAMS
PANEL_OAUTH_EXTRA_PARAMS[tenant_id]="<your-tenant-id>"
export PANEL_OAUTH_EXTRA_PARAMS
export PANEL_COOKIE_SECRET="<your-cookie-secret>"
export PANEL_OAUTH_ENCRYPTION="<your-encryption-key>"
```

### Launch (Local Development)

#### Option 1: Using uv (Recommended for quick iterative testing)

**Setup:**
```bash
uv venv --python 3.12
uv sync
```

**Set required environment variables:**
```bash
export BYPASS_CODEOCEAN_S3=1
export AWS_PROFILE="<your-profile>"
```

**Launch:**
```bash
panel serve src/aind_qc_portal/view.py src/aind_qc_portal/portal.py src/aind_qc_portal/status.py \
  --dev \
  --show \
  --port 5007 \
  --plugins aind_qc_portal.plugin \
  --static-dirs images=./src/aind_qc_portal/images \
  --oauth-redirect-uri="http://localhost:5007" \
  --oauth-optional \
  --index=portal \
  --num-threads 0
```

**Access the application:**
- Portal: http://localhost:5007/portal
- View: http://localhost:5007/view?name=<asset-name>

#### Option 2: Using Docker (Recommended for deployment testing)

Docker provides a closer match to the production deployment environment. Use this to test changes before they go live. 

**Prerequisites:**
- Docker installed and running
- AWS credentials configured in `~/.aws` (Windows: `%USERPROFILE%\.aws`)

**Build the Docker image:**
```bash
docker build -t aind-qc-portal .
```

**Run the container:**

For **Windows (Git Bash/MSYS2)**:
```bash
MSYS_NO_PATHCONV=1 docker run \
  -v $USERPROFILE/.aws:/root/.aws:ro \
  -e ALLOW_WEBSOCKET_ORIGIN=localhost:5007 \
  -e OAUTH_REDIRECT=http://localhost:5007 \
  -e AWS_PROFILE=<your-profile> \
  -e BYPASS_CODEOCEAN_S3=1 \
  -p 5007:8000 \
  aind-qc-portal
```

For **Linux/macOS**:
```bash
docker run \
  -v ~/.aws:/root/.aws:ro \
  -e ALLOW_WEBSOCKET_ORIGIN=localhost:5007 \
  -e OAUTH_REDIRECT=http://localhost:5007 \
  -e AWS_PROFILE=<your-profile> \
  -e BYPASS_CODEOCEAN_S3=1 \
  -p 5007:8000 \
  aind-qc-portal
```

**Access the application:**
- Portal: http://localhost:5007/portal
- View: http://localhost:5007/view?name=<asset-name>

**Note**: Unlike `panel serve --dev` with auto-reload, Docker requires rebuilding the image after each code change. For rapid iteration, use the `uv` method above. Use Docker primarily for final testing before deployment.


### Deployment in AWS

1. On pushes to the `dev` or `main` branch, a GitHub Action will run to publish a Docker image to `ghcr.io/allenneuraldynamics/aind-qc-portal:dev` or `ghcr.io/allenneuraldynamics/aind-qc-portal:latest`.
2. The image can be used by a ECS Service in AWS to run a task container. Application Load Balancer can be used to serve the container from ECS. Please note that the task must be configured with the correct env variables.
   - `ALLOW_WEBSOCKET_ORIGIN=qc.allenneuraldynamics.org`
   - `OAUTH_REDIRECT=https://qc.allenneuraldynamics.org`
   - `BYPASS_CODEOCEAN_S3` should **NOT** be set in production (AWS task role provides proper permissions)
