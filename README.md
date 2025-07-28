# Psion Software Index

[![build](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml/badge.svg)](https://github.com/jbmorley/psion-software-index/actions/workflows/build.yaml)

Tools for generating an index of Psion software

## Usage

Install the dependencies:

```bash
brew install p7zip
```

And then:

```bash
scripts/install-dependencies.sh
```

Download the assets:

```bash
tools/indexer libraries/full.yaml sync
```

Generate the index:

```bash
tools/indexer libraries/full.yaml index
```

Perform grouping:

```bash
tools/indexer libraries/full.yaml group
```

Apply the overlay:

```bash
tools/indexer libraries/full.yaml overlay
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
tools/indexer libraries/3lib.yaml sync index group overlay
```

You can serve the site locally as follows:

```bash
cd site
bundle exec jekyll serve --watch
```

Subsequent calls to update the index will cause the site to be rebuilt automatically.

**Note:** The indexer runs multiple commands and Lua scripts during the indexing process (approximately 100,000 for the current library). Small changes in process launch times can therefore significantly impact index generation performance, and shim-based environment managers like [asdf](https://asdf-vm.com) can cause real problems. To work around this, the indexer respects the `LUA_PATH` environment variable to allow shims to be bypassed. For example,

```bash
LUA_PATH=/opt/homebrew/bin/lua tools/indexer libraries/3lib.yaml sync index group overlay
```

## Contributing

Contributions are welcome in the form of PRs or GitHub Issues.

## References

- [Psion Software (Internet Archive)](https://archive.org/search?query=Psion)
