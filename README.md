# Psion Software Index

[![build](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml/badge.svg)](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml)

Tools for generating an index of Psion software

## Usage

### Checkout

```sh
git clone git@github.com:jbmorley/psion-software-index.git
cd psion-software-index
git submodule update --init --recursive
```

### Dependencies

```sh
mise trust
mise install
scripts/install-dependencies.sh
```

### Environment

The Cloudflare R2 bucket details and API key need to be available in the environment:

- `SNAPSHOTS_BUCKET_ENDPOINT_URL` – endpoint URL
- `SNAPSHOTS_BUCKET_NAME` – bucket name
- `SNAPSHOTS_BUCKET_ACCESS_KEY_ID` – access key id
- `SNAPSHOTS_BUCKET_SECRET_ACCESS_KEY` – secret access key

> [!IMPORTANT]
>
> When building the index in CI, a **read-only** access is sufficient, and read-write keys should **not** be used.

Both the `manage` and `indexer` commands will read from a `.env` file in the root of the repository. This can be useful for local development. For example,

``` sh
export SNAPSHOTS_BUCKET_ENDPOINT_URL="..."
export SNAPSHOTS_BUCKET_NAME="..."
export SNAPSHOTS_BUCKET_ACCESS_KEY_ID="..."
export SNAPSHOTS_BUCKET_SECRET_ACCESS_KEY="..."
```

### Build

Download the assets:

```bash
uv run indexer libraries/full.yaml sync
```

Generate the index:

```bash
uv run indexer libraries/full.yaml index
```

Perform grouping:

```bash
uv run indexer libraries/full.yaml group
```

Apply the overlay:

```bash
uv run indexer libraries/full.yaml overlay
```

Build the website:

```bash
scripts/build-site.sh
```

These steps are intentionally separated to make it easy to cache different phases of index generation, especially when using GitHub Actions.

## Deployments

This Software Index is hosted from a Cloudflare R2 bucket with a lightweight Worker, located in `workers`. The Worker is currently manually deployed as follows:

```sh
npx cf auth login
scripts/deploy-cloudflare.sh
```

## Development

It can be useful to be able to run the indexer on a smaller library:

```bash
uv run indexer libraries/small.yaml sync index group overlay
```

You can serve the site locally as follows:

```bash
cd site
bundle exec jekyll serve --watch
```

Building the site for the first time can be a bit slow, so be patient. Subsequent calls to update the index will cause the site to be rebuilt automatically.

> [!TIP]
> The indexer runs multiple commands and Lua scripts during the indexing process (approximately 100,000 for the current library). Small changes in process launch times can therefore significantly impact index generation performance, and shim-based environment managers like [asdf](https://asdf-vm.com) can cause real problems. To work around this, the indexer respects the `LUA_PATH` environment variable to allow shims to be bypassed. For example,
>
> ```bash
> LUA_PATH=/opt/homebrew/bin/lua uv run indexer libraries/small.yaml sync index group overlay
> ```

## Contributing

Contributions are welcome in the form of PRs or GitHub Issues.

### Content

The Software Index is built from snapshots contained within a private [Cloudflare R2](https://www.cloudflare.com/products/r2/) bucket. This guards against original sources disappearing, and to ensures we don't unnecessarily load primary hosts when generating the Index.

Content requests are tracked by #2.

We provide a CLI that can be used to create the following snapshot types:

- Website – a one-shot mirror of a website

  ```sh
  uv run manage add-snapshot https://psion.com
  ```

- Internet Archive – a copy of one or more assets from an Internet Archive item with associated metadata

  - Snapshot a complete item:

    ```sh
    uv run manage add-snapshot https://archive.org/details/palmtop-cd-2
    ```

  - Cherry-pick a single asset from an item:

    ```sh
    uv run manage add-snapshot https://archive.org/download/palmtop-cd-2/palmtop%20cd2.zip
    ```

> [!NOTE]
>
> The `manage` command requires a **read-write** [Cloudflare R2 API key](#environment) to allow snapshot uploads.

### Issues

- [Top-level issues](https://github.com/psion-community/psion-software-index/issues?q=is%3Aissue+state%3Aopen+no%3Aparent-issue) (`is:issue state:open no:parent-issue`)

## References

- [Psion Software (Internet Archive)](https://archive.org/search?tab=software&query=Psion)
