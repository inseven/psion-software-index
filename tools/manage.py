#!/usr/bin/env python3

# Copyright (c) 2024-2026 Jason Morley
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

import contextlib
import datetime
import getpass
import hashlib
import json
import logging
import os
import os
import shutil
import socket
import subprocess
import sys
import tempfile

from dataclasses import dataclass
from urllib.parse import quote, unquote
from urllib.parse import urlparse

import fastcommand
import requests
import yaml

import boto3
import requests

from bs4 import BeautifulSoup

from . import common
from . import utils

from .utils import InternetArchiveFile, InternetArchiveFiles, InternetArchiveMetdata
from .common import SnapshotType, SnapshotMetadata, UnknownSnapshotType, UnsupportedURL


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)
SNAPSHOTS_DIRECTORY = os.path.join(ROOT_DIRECTORY, "_snapshots")

DEFAULT_LIBRARY_PATH = os.path.join(ROOT_DIRECTORY, "libraries", "full.yaml")

CONFIG_PATH = os.path.expanduser("~/.config/psion-software-index/snapshot-config.json")

USER_AGENT = "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0"


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


def add_source(library_path, *source_urls):
    """
    Add `source_url` to the library at `library_path`.
    """
    with open(library_path) as fh:
        library = yaml.safe_load(fh)

    # Use a set to ensure uniqueness.
    sources = set(library["sources"])
    sources = sources.union(source_urls)

    # We always want the output to be sorted.
    library["sources"] = sorted(sources, key=str.casefold)

    with open(library_path, "w") as fh:
        yaml.dump(library, fh, sort_keys=False)


@fastcommand.command("add", help="add a source to the index", arguments=[
    fastcommand.Argument("url", help="source url")
])
def command_add(options):
    add_source(options.library, options.url)


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


def mirror_site(url, path, log_path):
    path = os.path.abspath(path)
    log_path = os.path.abspath(log_path)
    with tempfile.TemporaryDirectory() as temporary_directory, contextlib.chdir(temporary_directory):
        result = subprocess.run(["wget",
                                 "--execute", "robots=off",
                                 "--mirror",
                                 "--directory-prefix", "root",
                                 "--no-host-directories",
                                 "--user-agent", USER_AGENT,
                                 "-o", log_path,
                                 url])
        tar("root", path)
        return result.returncode


def tar(source, destination):
    command = [
        "tar",
        "-zcf", destination,
        "-C", source,
        "."
    ]
    subprocess.check_call(command)


@contextlib.contextmanager
def tar_container(path):
    path = os.path.abspath(path)
    with tempfile.TemporaryDirectory() as temporary_directory, contextlib.chdir(temporary_directory):
        yield temporary_directory
        logging.info("Compressing '%s'...", path)
        tar(temporary_directory, path)


@dataclass
class DocumentMetadata:
    title: str
    description: str


def get_document_metadata(url):
    response = requests.get(url, headers={
        "User-Agent": USER_AGENT,
    })
    document = BeautifulSoup(response.text, 'html.parser')
    title = document.title.text
    description = ""
    description_tag = document.select('meta[name="description"]')
    if description_tag:
        description = description_tag[0].attrs["content"]
    return DocumentMetadata(title=title, description=description)


def query(text):
    print(f"{text} [Y/n]")
    result = input().lower().strip()
    return result == "y" or result == ""


def upload(source_path, destination_filename):

    logging.info("Loading configuration...")
    with open(CONFIG_PATH) as fh:
        config = json.load(fh)

    logging.info("Uploading...")
    client = boto3.client("s3",
                          endpoint_url=config["endpoint_url"],
                          aws_access_key_id=config["access_key_id"],
                          aws_secret_access_key=config["secret_access_key"],
                          region_name="auto")
    client.upload_file(source_path,
                       config["bucket_name"],
                       destination_filename,
                       ExtraArgs={"ContentType": "application/gzip"})

    return f"snapshot:{destination_filename}"


@contextlib.contextmanager
def snapshot_container(path, metadata):
    with tar_container(path) as temporary_directory:
        with open("metadata.json", "w") as fh:
            metadata.dump(fh)
        yield temporary_directory


def infer_snapshot_type(url):
    url_components = urlparse(url)
    if url_components.hostname == "archive.org":
        return SnapshotType.INTERNET_ARCHIVE
    elif url_components.scheme in ["https", "http"]:
        return SnapshotType.WEBSITE
    else:
        raise UnsupportedURL(url)


@dataclass
class InternetArchiveSpec:
    """
    Specification describing an Internet Archive as inferred by parsing a URL.
    """
    identifier: str
    file: str | None

    @classmethod
    def parse(cls, url):
        """
        Parse a URL, `url`, describing an Internet Archive item or single asset from an item.
        """
        url_components = urlparse(url)
        if url_components.hostname != "archive.org":
            raise UnsupportedURL(url)
        path_components = url_components.path.split("/")[1:]
        if path_components[0] == "download" and len(path_components) == 3:
            return cls(identifier=path_components[1], file=unquote(path_components[2]))
        elif path_components[0] == "details" and len(path_components) == 2:
            return cls(identifier=path_components[1], file=None)
        raise UnsupportedURL(url)


def download_internet_archive_file(identifier, filename, path):
    url = f"https://archive.org/download/{identifier}/{quote(filename)}"
    logging.info("Downloading '%s'...", url)
    utils.download_file(url, path)


class InvalidChecksum(Exception):
    pass


def download_internet_archive_item(spec, destination_directory):

    # Metadata.
    logging.info("Downloading metadata...")
    item_metadata_filename = f"{spec.identifier}_meta.xml"
    item_metadata_path = os.path.join(destination_directory, item_metadata_filename)
    download_internet_archive_file(spec.identifier, item_metadata_filename, item_metadata_path)

    # Files.
    logging.info("Downloading file listing...")
    item_files_filename = f"{spec.identifier}_files.xml"
    item_files_path = os.path.join(destination_directory, item_files_filename)
    download_internet_archive_file(spec.identifier, item_files_filename, item_files_path)

    # Assets.
    logging.info("Downloading assets...")
    with open(item_files_path) as fh:
        file_listing = InternetArchiveFiles.load(fh)
    if spec.file is not None:
        files = [next(f for f in file_listing.files if f.name == spec.file)]
    else:
        files = [f for f in file_listing.files if f.source == "original" and f.format not in ["Metadata", "JPEG Thumb", "Item Tile"]]

    for f in files:
        file_path = os.path.join(destination_directory, f.name)
        download_internet_archive_file(spec.identifier, f.name, file_path)
        if f.sha1 != utils.digest(file_path, method=hashlib.sha1):
            raise InvalidChecksum(file_path)


@fastcommand.command("add-snapshot", help="create and upload a new website snapshot", arguments=[
    fastcommand.Argument("url", help="url to mirror"),
    fastcommand.Argument("-y", "--yes", action="store_true", default=False, help="automatically answer yes to all prompts"),
])
def command_add_snapshot(options):
    os.makedirs(SNAPSHOTS_DIRECTORY, exist_ok=True)
    url = options.url

    snapshot_type = infer_snapshot_type(url)
    if snapshot_type == SnapshotType.WEBSITE:

        identifier = urlparse(url).hostname
        document_metadata = get_document_metadata(url)
        snapshot_metadata = SnapshotMetadata(type=snapshot_type,
                                             url=url,
                                             identifier=identifier,
                                             title=document_metadata.title,
                                             description=document_metadata.description)

        def download(container_path):
            with contextlib.chdir(container_path):
                logging.info("Mirroring '%s'...", url)
                returncode = mirror_site(url, "contents.tar.gz", "log.txt")
                if returncode != 0:
                    logging.warning("wget exited with a non-zero exit code (%s); check log.txt for more details.", returncode)
                    if query("Review logs?"):
                        subprocess.run(["less", "log.txt"])
                else:
                    logging.info("wget completed successfully.")

    elif snapshot_type == SnapshotType.INTERNET_ARCHIVE:

        spec = InternetArchiveSpec.parse(url)
        item_metadata = InternetArchiveMetdata.get(spec.identifier)
        snapshot_metadata = SnapshotMetadata(type=snapshot_type,
                                             url=url,
                                             identifier=spec.identifier,
                                             title=item_metadata.title,
                                             description=item_metadata.description)

        def download(container_path):
            with contextlib.chdir(container_path), tar_container("contents.tar.gz") as contents_path:
                logging.info("Downloading '%s'...", spec.identifier)
                download_internet_archive_item(spec, contents_path)

    else:
        raise UnknownSnapshotType(snapshot_type)

    # Create the snapshot.
    snapshot_path = os.path.join(SNAPSHOTS_DIRECTORY, snapshot_metadata.filename)
    with snapshot_container(snapshot_path, snapshot_metadata) as container_path:
        download(container_path)

    # Upload.
    if options.yes or query("Upload and update library?"):
        url = upload(snapshot_path, snapshot_metadata.filename)
        add_source(options.library, url)

    logging.info("Done.")


def main():
    cli = fastcommand.CommandParser(description="Management tool for the Psion Software Index.")
    cli.add_argument("--library", help=f"path to the library (defaults to '{os.path.relpath(DEFAULT_LIBRARY_PATH)}')", default=DEFAULT_LIBRARY_PATH)
    cli.add_argument("--disable-ipv6", action="store_true", help="disable ipv6")
    cli.use_logging(format="[%(levelname)s] %(message)s")
    cli.run()


if __name__ == "__main__":
    main()
