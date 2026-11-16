# Psion Software Index

[![build](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml/badge.svg)](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml)

Tools for generating an index of Psion software

## Usage

Install the dependencies:

```bash
mise trust
mise install
```

And then:

```bash
scripts/install-dependencies.sh
```

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

## Development

Check out the source, remembering to clone the submodules:

```bash
git clone git@github.com:jbmorley/psion-software-index.git
cd psion-software-index
git submodule update --init --recursive
```

It can be useful to be able to run the indexer on a smaller library:

```bash
uv run indexer libraries/3lib.yaml sync index group overlay
```

You can serve the site locally as follows:

```bash
cd site
bundle exec jekyll serve --watch
```

Building the site for the first time can be a bit slow, so be patient. Subsequent calls to update the index will cause the site to be rebuilt automatically.

> [!NOTE]
> The indexer runs multiple commands and Lua scripts during the indexing process (approximately 100,000 for the current library). Small changes in process launch times can therefore significantly impact index generation performance, and shim-based environment managers like [asdf](https://asdf-vm.com) can cause real problems. To work around this, the indexer respects the `LUA_PATH` environment variable to allow shims to be bypassed. For example,
>
> ```bash
> LUA_PATH=/opt/homebrew/bin/lua uv run indexer libraries/3lib.yaml sync index group overlay
> ```

## Content

The Software Index can load content directly from the [Internet Archive](https://archive.org), or from structured snapshots available on a public-facing URL.

Snapshots are current stored in a public Backblaze B2 bucket (we are exploring moving to a private [Cloudflare R2](https://www.cloudflare.com/products/r2/) to avoid egress costs). They exist to guard against original sources disappearing, and to ensure we don't unnecessarily load primary hosts when generating the Index. They can be of the following types:

- Website – a one-shot mirror of a website
- Internet Archive – a copy of one or more assets from an Internet Archive item with associated metadata

The Index provides tooling to assist with the generation of snapshots.

### Website Snapshot

```sh
uv run manage add-snapshot https://surf.software
```

### Internet Archive Snapshot

While there is currently no single-step process for creating a snapshot from an Internet Archive item, a snapshot can be generated from an existing pre-synchronized item. For example,

```sh
uv run manage import --yes \
    _assets/NWTPsion3/NWTPsion3_meta.xml \
    _assets/NWTPsion5/NWTPsion5_meta.xml
```

## Contributing

Contributions are welcome in the form of PRs or GitHub Issues.

## References

- [Psion Software (Internet Archive)](https://archive.org/search?query=Psion)
