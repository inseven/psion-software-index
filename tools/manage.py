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

import getpass
import logging
import os
import socket
import subprocess

import fastcommand
import requests
import yaml

import common


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)

DEFAULT_LIBRARY_PATH = os.path.join(ROOT_DIRECTORY, "libraries", "full.yaml")


# https://stackoverflow.com/questions/33046733/force-requests-to-use-ipv4-ipv6#46972341
def force_ipv4():
    old_getaddrinfo = socket.getaddrinfo
    def new_getaddrinfo(*args, **kwargs):
        responses = old_getaddrinfo(*args, **kwargs)
        return [response
                for response in responses
                if response[0] == socket.AF_INET]
    socket.getaddrinfo = new_getaddrinfo


def process_network_options(options):
    if options.disable_ipv6:
        logging.info("Disabling IPv6...")
        force_ipv4()


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
    fastcommand.Argument("--id", help="new identifier to use (generated from search term if unspecified)"),
    fastcommand.Argument("-n", "--name", help="name of the new group (search term if unspecified)"),
    fastcommand.Argument("--platform", choices=["epoc16", "epoc32"], action="append", default=[], help="platforms to search for (defaults to epoc16 and epoc32)"),
    fastcommand.Argument("--pull", action="store_true", default=False, help="pull before making any changes"),
    fastcommand.Argument("--branch", action="store_true", default=False, help="create a new git branch for the update"),
    fastcommand.Argument("--prefix", help="prefix to use when creating a branch (defaults to the current username)"),
    fastcommand.Argument("--commit", action="store_true", default=False, help="commit the changes"),
    fastcommand.Argument("--create-pull-request", action="store_true", default=False, help="raise a new PR using the GitHub CLI"),
    fastcommand.Argument("--restore-branch", help="checkout the named branch after an update"),
    fastcommand.Argument("--cleanup", action="store_true", default=False, help="delete the working branch"),
    fastcommand.Argument("--auto", action="store_true", default=False, help="equivalent of --pull --branch --commit --create-pull-request --restore-branch main --delete-branch"),
])
def command_group(options):
    process_network_options(options)
    library = common.Library(options.library)
    if options.auto:
        options.pull = True
        options.branch = True
        options.commit = True
        options.create_pull_request = True
        options.restore_branch = "main"
        options.cleanup = True
    id = options.id if options.id is not None else options.search.lower().replace(" ", "-")
    name = options.name if options.name is not None else options.search
    prefix = options.prefix if options.prefix is not None else getpass.getuser()
    platforms = set(options.platform if options.platform else ["epoc16", "epoc32"])

    response = requests.get("https://software.psion.community/api/v1/groups/")
    groups = response.json()
    groups = [group for group in groups if options.search.lower() in group["name"].lower() and platforms.intersection(group["platforms"])]
    if not groups:
        exit("No matches found.")

    print("Found:")
    for group in groups:
        platforms = ", ".join(group["platforms"])
        print(f"- {group["id"]}: {group["name"]} ({platforms})")
    answer = input("Continue? [yN] ")
    if answer != "y":
        exit("Aborting...")

    if options.pull:
        logging.info("Pulling...")
        subprocess.check_call(["git", "pull"])

    if options.branch:
        branch = f"{prefix}/group-{id}"
        logging.info("Creating '%s'...", branch)
        subprocess.check_call(["git", "checkout", "-b", branch])

    overlay_directory = os.path.join(library.overlay_directories[0], f"id_{id}")
    os.makedirs(overlay_directory, exist_ok=True)
    overlay_path = os.path.join(overlay_directory, "index.md")
    with open(overlay_path, "w") as fh:
        fh.write("---\n")
        fh.write(f"name: {name}\n")
        fh.write("ids:\n")
        for group in groups:
            platforms = ", ".join(group["platforms"])
            fh.write(f"- {group["id"]}  # {group["name"]} ({platforms})\n")
        fh.write("---\n")

    if options.commit:
        logging.info("Committing changes...")
        subprocess.check_call(["git", "add", overlay_path])
        subprocess.check_call(["git", "commit", "-m", f"fix(data): Group '{name}'"])

        if options.create_pull_request:
            logging.info("Creating pull request...")
            subprocess.check_call(["gh", "pr", "create", "-w"])

        if options.branch and options.restore_branch:
            logging.info("Checking out '%s'...", options.restore_branch)
            subprocess.check_call(["git", "checkout", options.restore_branch])

            if options.cleanup:
                logging.info("Deleting working branch...")
                subprocess.check_call(["git", "branch", "-D", branch])


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
    cli.add_argument("--disable-ipv6", action="store_true", help="disable ipv6")
    cli.use_logging(format="[%(levelname)s] %(message)s")
    cli.run()


if __name__ == "__main__":
    main()
