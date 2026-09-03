# Installation

OTC supports Python 3.11 through 3.14. The CLI is published as the
`open-table-connector` distribution and exposes `otc` and
`open-table-connector` entry points.

## Install a release

```console
uv tool install open-table-connector
otc --help
```

Install provider packages separately when you need them. The core CLI and SDK
do not install every remote connector:

```console
python -m pip install open-table-connector-sdk
python -m pip install open-table-connector-local-files
python -m pip install open-table-connector-timeseries
python -m pip install open-table-connector-sqlite
```

PostgreSQL support has an optional live dependency:

```console
python -m pip install 'open-table-connector-postgres[live]'
```

## Install from a checkout

```console
git clone https://github.com/OmniMCP-AI/open-table-connector.git
cd open-table-connector
uv sync --all-packages --group dev
source .venv/bin/activate
otc --help
```

`--all-packages` is important: this workspace contains independently packaged
connectors as well as the CLI. `uv sync` alone is not the complete checkout
setup.

## Verify the workspace

```console
otc list
python -c 'import open_table_connector.sdk as otc; print(otc.Client)'
uv run pytest -q
```

The CLI discovers installed provider descriptors. A provider that is not
installed cannot be selected by a URI, even if its URI scheme is known in a
design document.

## Optional process deployment

Install the process package when OTS or another caller needs a separate local
connector process:

```console
uv run --package open-table-connector-process otc-process --help
```

The process uses a deployment-owned configuration file and artifact root; see
[Deployment](../operations/deployment.md) and [Security](../operations/security.md).
