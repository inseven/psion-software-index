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
import enum
import json
import logging
import os
import shutil
import sys
import tempfile

from dataclasses import dataclass
from urllib.parse import quote_plus
from urllib.parse import urlparse

import boto3
import yaml

import xml.etree.ElementTree as ET

from . import containers
from . import model
from . import utils


SNAPSHOT_PREFIX = "snapshot:"


ARCHIVE_EXTENSIONS = set([
    ".zip",
    ".iso",
])


class UnsupportedURL(Exception):
    pass


class UnknownSnapshotType(Exception):
    pass


class SnapshotType(enum.StrEnum):
    WEBSITE = "website"
    INTERNET_ARCHIVE = "internet-archive"


@dataclass
class SnapshotMetadata:
    date: datetime
    type: SnapshotType
    url: str
    identifier: str
    title: str
    description: str

    def __init__(self, type, url, identifier, title, description):
        self.date = datetime.datetime.now(datetime.timezone.utc)
        self.type = type
        self.url = url
        self.identifier = identifier
        self.title = title
        self.description = description

    @classmethod
    def load(cls, fh):
        contents = json.load(fh)
        date = contents["created"]
        type = SnapshotType(contents["type"]) if "type" in contents else SnapshotType.WEBSITE
        url = contents["url"]
        identifier = contents["identifier"] if "identifier" in contents else None
        title = contents["title"]
        description = contents["description"] if "description" in contents else ""

        snapshot = cls(type=type,
                       url=url,
                       identifier=identifier,
                       title=title,
                       description=description)
        snapshot.date = date
        return snapshot


    @property
    def filename(self):
        timestamp = self.date.strftime("%Y-%m-%d-%H-%M-%S")
        return f"{timestamp}-{self.type}-{self.identifier.replace(" ", "-")}.tar.gz"

    def dump(self, fh):
        json.dump({
            "created": self.date.isoformat(),
            "type": self.type,
            "url": self.url,
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
        }, fh, indent=4)
        fh.write("\n")


def create_source(assets_directory, url):
    if os.path.isdir(url):
        return LocalSource(assets_directory, url)
    url_components = urlparse(url)
    if url_components.hostname == "archive.org":
        return InternetArchiveSource(assets_directory, url)
    elif url.startswith(SNAPSHOT_PREFIX):
        return SnapshotSource(assets_directory, url)
    raise UnsupportedURL(url)


class Library(object):

    def __init__(self, path):
        self.path = os.path.abspath(path)
        with open(path) as fh:
            self._configuration = yaml.safe_load(fh)
        root_directory = os.path.dirname(self.path)
        self.overlay_directories = [os.path.normpath(os.path.join(root_directory, overlay_directory))
                                    for overlay_directory in self._configuration['overlays']]

        def prefer_environment_variable(key):
            """
            Return the value of the environment variable for `key` if set; otherwise, return the library configuration
            for `key`, resolved against to the root of the library root directory.

            The environment variable name is the uppercased key, prefixed with `INDEXER_`.
            """
            environment_variable_name = f"INDEXER_{key}".upper()
            if environment_variable_name in os.environ:
                value = os.environ[environment_variable_name]
                logging.warning("Using $%s environment variable (%s)", environment_variable_name, value)
                return value
            return os.path.normpath(os.path.join(root_directory, self._configuration[key]))

        self.assets_directory = prefer_environment_variable("assets_directory")
        self.intermediates_directory = prefer_environment_variable("intermediates_directory")
        self.index_directory = prefer_environment_variable("index_directory")
        self.filetree_directory = prefer_environment_variable("filetree_directory")
        self.output_directory = prefer_environment_variable("output_directory")
        self.sources = [create_source(self.assets_directory, url) for url in self._configuration['sources']]

    def sync(self):
        logging.info("Syncing library...")
        for source in self.sources:
            source.sync()

    @property
    def blocked_identifiers(self):
        if 'blocked_identifiers' not in self._configuration:
            return []
        return self._configuration['blocked_identifiers']


# This collection of messy little helper functions ensures that the returned references have valid download
# URLs. The work is delegated to the sources as they know how to generate source-specific download URLs (at
# least until we start caching assets somewhere else).
def internet_archive_reference_resolver(internet_archive_identifier, title):
    source_reference = model.ReferenceItem(name=title, url=f"https://archive.org/details/{internet_archive_identifier}")

    def reference_resolver(reference):

        def resolve_root_url(reference):
            return f"https://archive.org/download/{internet_archive_identifier}/{reference[0].name}"

        def resolve_root_reference_item(reference_item, root_url):
            return model.ReferenceItem(name=reference_item.name, url=root_url)

        # TODO: Not all first-level containers (e.g., .bin) can be accessed on the Internet Archive.
        def resolve_first_tier_reference_item(reference_item, root_url):
            return model.ReferenceItem(name=reference_item.name,
                                       url=root_url + "/" + quote_plus(reference_item.name))

        if len(reference) < 1:
            return [source_reference]
        if len(reference) == 1:
            root_url = resolve_root_url(reference)
            return [source_reference, resolve_root_reference_item(reference[0], root_url)]
        else:
            root, first_tier, *tail = reference
            root_url = resolve_root_url(reference)
            return [source_reference, resolve_root_reference_item(root, root_url)] + [resolve_first_tier_reference_item(first_tier, root_url)] + tail

    return reference_resolver


def website_reference_resolver(url, title):
    source_reference = model.ReferenceItem(name=title, url=url)

    def make_link(reference):
        url_components = urlparse(url)
        base_path = url_components.path
        if not base_path.endswith("/"):  # Ensure there's a trailing directory marker.
            base_path += "/"
        name = reference.name[len(base_path)-1:]
        return model.ReferenceItem(name=name, url=f"{url_components.scheme}://{url_components.netloc}/{reference.name}")

    def resolve_reference(reference):
        if len(reference) < 1:
            return [source_reference]
        else:
            return [source_reference] + [make_link(reference[0])] + reference[1:]

    return resolve_reference


class InternetArchiveSource(object):

    def __init__(self, root_directory, url):
        self.url = url
        url_components = urlparse(url)

        # We currently support a few different Internet Archive url formats:
        # - item urls
        # - download urls

        if url_components.hostname != "archive.org":
            raise UnsupportedURL(url)
        path_components = url_components.path.split("/")[1:]
        if path_components[0] == "download":

            # We don't currently support downloading paths inside archives.
            for component in path_components[:-1]:
                if os.path.splitext(component)[1].lower() in ARCHIVE_EXTENSIONS:
                    raise UnsupportedURL(url)
            internet_archive_identifier = path_components[1]
            identifier = "+".join(path_components[1:])
        elif path_components[0] == "details" and len(path_components) == 2:
            internet_archive_identifier = path_components[1]
            identifier = path_components[1]
        else:
            raise UnsupportedURL(url)

        self.internet_archive_identifier = internet_archive_identifier
        self.identifier = utils.safe_identifier("internet-archive-" + identifier)
        self.item_directory = os.path.join(root_directory, self.internet_archive_identifier)
        self.item_metadata_path = os.path.join(self.item_directory, f"{self.internet_archive_identifier}_meta.xml")
        self.file_metadata_path = os.path.join(self.item_directory, f"{self.internet_archive_identifier}_files.xml")
        self.relative_path = os.path.join(*(path_components[2:]))
        self.path = os.path.join(self.item_directory, self.relative_path)
        self._metadata = None

    def sync(self):
        logging.info("Syncing '%s'...", self.internet_archive_identifier)
        os.makedirs(self.item_directory, exist_ok=True)
        if not os.path.exists(self.item_metadata_path):
            utils.download_file_with_mirrors([
                f"https://archive.org/download/{self.internet_archive_identifier}/{self.internet_archive_identifier}_meta.xml",
            ], self.item_metadata_path)
        if not os.path.exists(self.file_metadata_path):
            utils.download_file_with_mirrors([
                f"https://archive.org/download/{self.internet_archive_identifier}/{self.internet_archive_identifier}_files.xml",
            ], self.file_metadata_path)
        if not os.path.exists(self.path):
            destination_directory = os.path.dirname(self.path)
            logging.info(destination_directory)
            os.makedirs(destination_directory, exist_ok=True)
            utils.download_file_with_mirrors([
                self.url,
            ], self.path)

    @property
    def hash(self):
        return utils.shasum(self.path)

    @property
    def metadata(self):
        if self._metadata is None:
            with open(self.item_metadata_path) as fh:
                self._metadata = utils.InternetArchiveMetdata.load(fh)
        return self._metadata

    @property
    def title(self):
        return self.metadata.title

    @property
    def description(self):
        return self.metadata.description

    @property
    def assets(self):
        resolve_reference = internet_archive_reference_resolver(self.internet_archive_identifier, self.title)
        for path, reference in containers.walk(self.path, relative_to=self.item_directory):
            yield (path, resolve_reference(reference))

    def as_dict(self):
        return {
            'kind': SnapshotType.INTERNET_ARCHIVE,
            'name': self.title,
            'description': self.description,
            'url': self.url,
            'html_url': f"https://archive.org/details/{self.internet_archive_identifier}"
        }


class SnapshotSource(object):

    def __init__(self, root_directory, url):
        self.root_directory = root_directory
        self.url = url
        if not url.startswith(SNAPSHOT_PREFIX) or not url.endswith(".tar.gz"):
            raise UnsupportedURL(url)

        if url.startswith(SNAPSHOT_PREFIX):
            filename = url.split(":", 1)[1]
        else:
            url_components = urlparse(url)
            filename = url_components.path.split("/")[-1]

        basename = filename[:-(len(".tar.gz"))]
        identifier = basename.replace("+", " ")

        self.path = os.path.join(root_directory, "snapshots", identifier)
        self.identifier = utils.safe_identifier("snapshot-" + identifier)
        self._contents_path = os.path.join(self.path, "contents.tar.gz")
        self._metadata_path = os.path.join(self.path, "metadata.json")
        self._metadata = None

    def _download(self, destination_directory):
        filename = self.url.split(":", 1)[1]

        endpoint_url = os.environ["SNAPSHOTS_BUCKET_ENDPOINT_URL"]
        bucket_name = os.environ["SNAPSHOTS_BUCKET_NAME"]
        access_key_id = os.environ["SNAPSHOTS_BUCKET_ACCESS_KEY_ID"]
        secret_access_key = os.environ["SNAPSHOTS_BUCKET_SECRET_ACCESS_KEY"]

        logging.info("Downloading '%s' from '%s'...", filename, bucket_name)
        client = boto3.client("s3",
                              endpoint_url=endpoint_url,
                              aws_access_key_id=access_key_id,
                              aws_secret_access_key=secret_access_key,
                              region_name="auto")
        destination_path = os.path.join(destination_directory, filename)
        client.download_file(bucket_name, filename, destination_path)
        return destination_path

    def sync(self):
        logging.info("Syncing '%s'...", self.url)
        if os.path.exists(self.path):
            return
        with tempfile.TemporaryDirectory() as temporary_directory, contextlib.chdir(temporary_directory):
            print("Creating directory...")
            filename = self._download(temporary_directory)
            contents_path = os.path.join(temporary_directory, "contents")
            os.makedirs(contents_path)
            containers.extract_tar_gz(filename, contents_path)
            shutil.move(contents_path, self.path)

    @property
    def hash(self):
        return utils.shasum(self.path)

    @property
    def metadata(self):
        if self._metadata is None:
            with open(self._metadata_path) as fh:
                self._metadata = SnapshotMetadata.load(fh)
        return self._metadata

    @property
    def title(self):
        return self.metadata.title

    @property
    def description(self):
        return self.metadata.description

    @property
    def kind(self):
        """
        Convert the snapshot type to the legacy 'kind' string enumeration.

        Exists to preserve API backwards compatibility.
        """
        if self.metadata.type == SnapshotType.INTERNET_ARCHIVE:
            return "internet-archive"
        elif self.metadata.type == SnapshotType.WEBSITE:
            return "snapshot"
        else:
            raise UnknownSnapshotType(self.metadata.type)

    @property
    def assets(self):
        snapshot_type = self.metadata.type
        if snapshot_type == SnapshotType.WEBSITE:
            resolve_reference = website_reference_resolver(self.metadata.url, self.title)
        elif snapshot_type == SnapshotType.INTERNET_ARCHIVE:
            resolve_reference = internet_archive_reference_resolver(self.metadata.identifier, self.title)
        else:
            raise UnknownSnapshotType(snapshot_type)
        with containers.get_extractor(self._contents_path) as contents_path:
            for path, reference in containers.walk(contents_path, relative_to=contents_path):
                yield path, resolve_reference(reference)

    def as_dict(self):
        return {
            "kind": self.kind,
            "name": self.title,
            "description": self.description,
            "html_url": self.metadata.url,
        }
