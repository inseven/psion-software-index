#!/usr/bin/env python3

# Copyright (c) 2024-2025 Jason Morley
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import os

import fastcommand
import requests
import yaml

import common


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)

DEFAULT_LIBRARY_PATH = os.path.join(ROOT_DIRECTORY, "libraries", "full.yaml")


@fastcommand.command("add", help="add a source to the index", arguments=[
    fastcommand.Argument("url", help="source url")
])
def command_add(options):

    # Load the library.
    with open(options.library) as fh:
        library = yaml.safe_load(fh)

    # Use a set to ensure uniqueness.
    sources = set(library["sources"])
    sources.add(options.url)

    # We always want the output to be sorted.
    library["sources"] = sorted(sources, key=str.casefold)

    for source in library["sources"]:
        print(source)

    with open(options.library, "w") as fh:
        yaml.dump(library, fh)


@fastcommand.command("group", help="generate a grouping file for programs matching a partial search term", arguments=[
    fastcommand.Argument("search", help="search term"),
    fastcommand.Argument("id", help="new identifier to use"),
    fastcommand.Argument("-n", "--name", help="name of the new group"),
])
def command_group(options):

    library = common.Library(options.library)
    name = options.name if options.name is not None else options.search

    response = requests.get("https://software.psion.community/api/v1/groups")
    groups = response.json()
    groups = [group for group in groups if options.search.lower() in group["name"].lower()]

    overlay_directory = os.path.join(library.overlay_directories[0], f"id_{options.id}")
    os.makedirs(overlay_directory, exist_ok=True)
    with open(os.path.join(overlay_directory, "index.md"), "w") as fh:
        fh.write("---\n")
        fh.write(f"name: {name}\n")
        fh.write("ids:\n")
        for group in groups:
            fh.write(f"- {group["id"]}  # {group["name"]}\n")
        fh.write("---\n")


@fastcommand.command("search", help="search all sources for a file", arguments=[
    fastcommand.Argument("name", help="file name to search for (case insensitive)")
])
def command_search(options):
    results = []
    library = common.Library(options.library)
    for source in library.sources:
        for (file_path, reference) in source.assets:
            basename = os.path.basename(file_path)
            if basename.lower() != options.name.lower():
                continue
            results.append((file_path, reference))

    print("")
    print("Search Results")
    print("==============")

    if not results:
        exit("No items found.")

    for (file_path, reference) in results:
        print(" -> ".join([item.name for item in reference] + [basename]))


def main():
    cli = fastcommand.CommandParser(description="Management tool for the Psion Software Index.")
    cli.add_argument("--library", help=f"path to the library (defaults to '{os.path.relpath(DEFAULT_LIBRARY_PATH)}')", default=DEFAULT_LIBRARY_PATH)
    cli.use_logging(format="[%(levelname)s] %(message)s")
    cli.run()


if __name__ == "__main__":
    main()
