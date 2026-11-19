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
uv run indexer libraries/small.yaml sync index group overlay
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
> LUA_PATH=/opt/homebrew/bin/lua uv run indexer libraries/small.yaml sync index group overlay
> ```

## Contributing

Contributions are welcome in the form of PRs or GitHub Issues.

### Content

The Software Index is built from snapshots contained within a private [Cloudflare R2](https://www.cloudflare.com/products/r2/) bucket. This guards against original sources disappearing, and to ensures we don't unnecessarily load primary hosts when generating the Index.

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

## References

- [Psion Software (Internet Archive)](https://archive.org/search?query=Psion)
