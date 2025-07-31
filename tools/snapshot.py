#!/usr/bin/env python3

# Copyright (c) 2024 Jason Morley
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
import json
import logging
import os
import subprocess
import sys
import tempfile

from urllib.parse import urlparse

import b2sdk.v2 as b2
import requests

from bs4 import BeautifulSoup


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)
SNAPSHOTS_DIRECTORY = os.path.join(ROOT_DIRECTORY, "_snapshots")

CONFIG_PATH = os.path.expanduser("~/.config/psion-software-index/snapshot-config.json")


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
                                 "--user-agent", "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
                                 "-o", log_path,
                                 url])
        tar("root", path)
        return result.returncode


def tar(source, destination):
    subprocess.check_call(["tar",
                           "-zcf",
                           destination,
                           "-C", source,
                           "."])


def get_title(url):
    response = requests.get(url)
    document = BeautifulSoup(response.text, 'html.parser')
    return document.title.text


def query(text):
    print(f"{text} [Y/n]")
    result = input().lower().strip()
    return result == "y" or result == ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    options = parser.parse_args()

    url = options.url
    url_components = urlparse(url)
    hostname = url_components.hostname

    date = datetime.datetime.now(datetime.timezone.utc)
    timestamp = date.strftime("%Y-%m-%d %H-%M-%S")
    filename = f"{timestamp} {hostname}.tar.gz"

    os.makedirs(SNAPSHOTS_DIRECTORY, exist_ok=True)

    archive_path = os.path.join(SNAPSHOTS_DIRECTORY, filename)

    with tempfile.TemporaryDirectory() as temporary_directory, contextlib.chdir(temporary_directory):

        # Ensure we can get the title.
        title = get_title(url)

        # Create an archive of the site.
        returncode = mirror_site(url, "contents.tar.gz", "log.txt")

        # Write the metadata.
        metadata = {
            "url": url,
            "title": title,
            "created": date.isoformat(),
        }
        with open("metadata.json", "w") as fh:
            json.dump(metadata, fh, indent=4)
            fh.write("\n")

        # Generate the archive.
        tar(temporary_directory, archive_path)

        # Warn if the mirror returned errors.
        if returncode != 0:
            logging.warning("wget exited with a non-zero exit code (%s); check log.txt for more details.", returncode)
            # Let the user review the logs.
            if query("Review logs?"):
                subprocess.run(["less", "log.txt"])
        else:
            logging.info("wget completed successfully.")

    # Upload the file.
    if query("Upload to B2?"):

        logging.info("Loading configuration...")
        with open(CONFIG_PATH) as fh:
            config = json.load(fh)

        logging.info("Uploading...")
        info = b2.InMemoryAccountInfo()
        b2_api = b2.B2Api(info)
        b2_api.authorize_account("production", config["key_id"], config["application_key"])
        bucket = b2_api.get_bucket_by_name("psion-software-index-snapshots")
        upload = bucket.upload_local_file(local_file=archive_path,
                                          file_name=filename,
                                          file_infos={})
        url = f"{b2_api.account_info.get_download_url()}/file/{bucket.name}/{upload.file_name.replace(" ", "+")}"
        print(url)

    logging.info("Done.")


if __name__ == "__main__":
    main()
