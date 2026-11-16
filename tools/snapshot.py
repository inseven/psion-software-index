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

import argparse
import contextlib
import datetime
import hashlib
import json
import logging
import os
import subprocess
import shutil
import sys
import tempfile

from urllib.parse import quote
from urllib.parse import urlparse

import fastcommand

import b2sdk.v2 as b2
import requests

from bs4 import BeautifulSoup

from .common import SnapshotType, SnapshotMetadata
from . import utils


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)
SNAPSHOTS_DIRECTORY = os.path.join(ROOT_DIRECTORY, "_snapshots")

CONFIG_PATH = os.path.expanduser("~/.config/psion-software-index/snapshot-config.json")

USER_AGENT = "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0"


verbose = '--verbose' in sys.argv[1:] or '-v' in sys.argv[1:]
logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="[%(levelname)s] %(message)s")


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


def get_title(url):
    response = requests.get(url, headers={
        "User-Agent": USER_AGENT,
    })
    document = BeautifulSoup(response.text, 'html.parser')
    return document.title.text


def query(text):
    print(f"{text} [Y/n]")
    result = input().lower().strip()
    return result == "y" or result == ""


def upload(source_path, destination_filename):

    logging.info("Loading configuration...")
    with open(CONFIG_PATH) as fh:
        config = json.load(fh)

    logging.info("Uploading...")
    info = b2.InMemoryAccountInfo()
    b2_api = b2.B2Api(info)
    b2_api.authorize_account("production", config["key_id"], config["application_key"])
    bucket = b2_api.get_bucket_by_name("psion-software-index-snapshots")
    upload = bucket.upload_local_file(local_file=source_path,
                                    file_name=destination_filename,
                                    file_infos={})

    return f"{b2_api.account_info.get_download_url()}/file/{bucket.name}/{upload.file_name.replace(" ", "+")}"


@contextlib.contextmanager
def snapshot_container(path, metadata):
    with tar_container(path) as temporary_directory:
        with open("metadata.json", "w") as fh:
            metadata.dump(fh)
        yield temporary_directory


@fastcommand.command("snapshot", help="create and upload a new website snapshot", arguments=[
    fastcommand.Argument("url", help="url to mirror")
])
def command_snapshot(options):
    os.makedirs(SNAPSHOTS_DIRECTORY, exist_ok=True)
    url = options.url

    # Create the snapshot.
    snapshot_metadata = SnapshotMetadata(type=SnapshotType.WEBSITE,
                                         url=url,
                                         identifier=urlparse(url).hostname,
                                         title=get_title(url),
                                         description="")
    snapshot_path = os.path.join(SNAPSHOTS_DIRECTORY, snapshot_metadata.filename)
    with snapshot_container(snapshot_path, snapshot_metadata) as container_path:
        returncode = mirror_site(url, "contents.tar.gz", "log.txt")
        if returncode != 0:
            logging.warning("wget exited with a non-zero exit code (%s); check log.txt for more details.", returncode)
            if query("Review logs?"):
                subprocess.run(["less", "log.txt"])
        else:
            logging.info("wget completed successfully.")

    # Upload.
    if query("Upload to B2?"):
        url = upload(snapshot_path, snapshot_metadata.filename)
        print(url)

    logging.info("Done.")


@fastcommand.command("import", help="import an existing Internet Archive asset", arguments=[
    fastcommand.Argument("metadata", help="path to downloaded asset metadata file")
])
def command_import(options):
    os.makedirs(SNAPSHOTS_DIRECTORY, exist_ok=True)
    metadata_path = os.path.abspath(options.metadata)
    assets_directory = os.path.dirname(metadata_path)

    # Read the metadata and file listing.
    with open(metadata_path) as fh:
        metadata = utils.InternetArchiveMetdata.load(fh)
    files_path = os.path.join(assets_directory, f"{metadata.identifier}_files.xml")
    with open(files_path) as fh:
        files = utils.InternetArchiveFiles.load(fh)

    # Check the files on disk.
    assets = []
    for f in files.files:
        file_path = os.path.join(assets_directory, quote(f.name))
        if f.format == "Metadata" or not os.path.exists(file_path):
            continue
        logging.info("Checking '%s'...", file_path)
        if f.sha1 != utils.digest(file_path, method=hashlib.sha1):
            exit("sha1 doesn't match.")
        assets.append(file_path)

    # Don't create a snapshot if there are no files.
    if len(assets) < 1:
        exit("No files found.")

    # Create the snapshot.
    snapshot_metadata = SnapshotMetadata(type=SnapshotType.INTERNET_ARCHIVE,
                                         url=f"https://archive.org/details/{metadata.identifier}",
                                         identifier=metadata.identifier,
                                         title=metadata.title,
                                         description=metadata.description)
    snapshot_path = os.path.join(SNAPSHOTS_DIRECTORY, snapshot_metadata.filename)
    with snapshot_container(snapshot_path, snapshot_metadata):
        with tar_container("contents.tar.gz") as container_path:
            for asset_path in assets + [metadata_path, files_path]:
                name = os.path.basename(asset_path)
                logging.info("Copying '%s'...", name)
                shutil.copyfile(asset_path, name)

    # Upload.
    if query("Upload to B2?"):
        url = upload(snapshot_path, snapshot_metadata.filename)
        print(url)

    logging.info("Done.")


def main():
    cli = fastcommand.CommandParser(description="Generate and upload source snapshots.")
    cli.use_logging(format="[%(levelname)s] %(message)s")
    cli.run()


if __name__ == "__main__":
    main()
