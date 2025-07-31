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

import contextlib
import json
import logging
import os
import shutil
import sys
import tempfile

from urllib.parse import quote_plus
from urllib.parse import urlparse

import yaml

import xml.etree.ElementTree as ET

import containers
import model
import utils


SNAPSHOTS_BASE_URL = "https://f002.backblazeb2.com/file/psion-software-index-snapshots/"


ARCHIVE_EXTENSIONS = set([
    ".zip",
    ".iso",
])


class UnsupportedURL(Exception):
    pass


def create_source(assets_directory, url):
    url_components = urlparse(url)
    if url_components.hostname == "archive.org":
        return InternetArchiveSource(assets_directory, url)
    elif url.startswith(SNAPSHOTS_BASE_URL):
        return SnapshotSource(assets_directory, url)
    raise UnsupportedURL(url)


class Library(object):

    def __init__(self, path):
        self.path = os.path.abspath(path)
        with open(path) as fh:
            self._configuration = yaml.safe_load(fh)
        root_directory = os.path.dirname(self.path)
        self.overlay_directories = [os.path.join(root_directory, overlay_directory)
                                    for overlay_directory in self._configuration['overlays']]
        self.assets_directory = os.path.normpath(os.path.join(root_directory, self._configuration['assets_directory']))
        if "INDEXER_ASSETS_DIRECTORY" in os.environ:
            self.assets_directory = os.environ["INDEXER_ASSETS_DIRECTORY"]
            logging.warning("Using $INDEXER_ASSETS_DIRECTORY environment variable (%s)", self.assets_directory)
        self.intermediates_directory = os.path.normpath(os.path.join(root_directory, self._configuration['intermediates_directory']))
        self.index_directory = os.path.normpath(os.path.join(root_directory, self._configuration['index_directory']))
        self.output_directory = os.path.normpath(os.path.join(root_directory, self._configuration['output_directory']))
        self.sources = [create_source(self.assets_directory, url) for url in self._configuration['sources']]

    def sync(self):
        logging.info("Syncing library...")
        for source in self.sources:
            source.sync()


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
            id = path_components[1]
        elif path_components[0] == "details" and len(path_components) == 2:
            id = path_components[1]
        else:
            raise UnsupportedURL(url)

        self.id = id
        self.item_directory = os.path.join(root_directory, self.id)
        self.item_metadata_path = os.path.join(self.item_directory, f"{self.id}_meta.xml")
        self.file_metadata_path = os.path.join(self.item_directory, f"{self.id}_files.xml")
        self.relative_path = os.path.join(*(path_components[2:]))
        self.path = os.path.join(self.item_directory, self.relative_path)
        self._metadata = None

    def sync(self):
        logging.info("Syncing '%s'...", self.id)
        os.makedirs(self.item_directory, exist_ok=True)
        if not os.path.exists(self.item_metadata_path):
            utils.download_file_with_mirrors([
                f"https://archive.org/download/{self.id}/{self.id}_meta.xml",
                f"https://psion.solarcene.community/{self.id}/{self.id}_meta.xml",
            ], self.item_metadata_path)
        if not os.path.exists(self.file_metadata_path):
            utils.download_file_with_mirrors([
                f"https://archive.org/download/{self.id}/{self.id}_files.xml",
                f"https://psion.solarcene.community/{self.id}/{self.id}_files.xml",
            ], self.file_metadata_path)

    @property
    def metadata(self):
        if self._metadata is None:
            with open(self.item_metadata_path) as fh:
                root = ET.fromstring(fh.read())
                self._metadata = {
                    'title': root.find('./title').text,
                    'description': root.find('./description').text,
                }
        return self._metadata

    @property
    def title(self):
        return self.metadata['title']

    @property
    def description(self):
        return self.metadata['description']

    @property
    def assets(self):

        # This collection of messy little helper functions ensures that the returned references have valid download
        # URLs. The work is delegated to the sources as they know how to generate source-specific download URLs (at
        # least until we start caching assets somewhere else).

        source_reference = model.ReferenceItem(name=self.title, url=f"https://archive.org/details/{self.id}")

        def resolve_reference(reference):

            def resolve_root_reference_item(reference_item):
                return model.ReferenceItem(name=reference_item.name, url=self.url)

            # TODO: Not all first-level containers (e.g., .bin) can be accessed on the Internet Archive.
            def resolve_first_tier_reference_item(reference_item):
                return model.ReferenceItem(name=reference_item.name,
                                           url=self.url + "/" + quote_plus(reference_item.name))

            if len(reference) < 1:
                return [source_reference]
            if len(reference) == 1:
                return [source_reference, resolve_root_reference_item(reference[0])]
            else:
                root, first_tier, *tail = reference
                return [source_reference, resolve_root_reference_item(root)] + [resolve_first_tier_reference_item(first_tier)] + tail

        for path, reference in containers.walk(self.path, relative_to=self.item_directory):
            yield (path, resolve_reference(reference))

    def as_dict(self):
        return {
            'path': self.path,
            'name': self.title,
            'description': self.description,
            'url': self.url,
            'html_url': f"https://archive.org/details/{self.id}"
        }


class SnapshotSource(object):

    def __init__(self, root_directory, url):
        self.root_directory = root_directory
        self.url = url
        if not url.startswith(SNAPSHOTS_BASE_URL) or not url.endswith(".tar.gz"):
            raise UnsupportedURL(url)
        url_components = urlparse(url)
        filename = url_components.path.split("/")[-1]
        basename = filename[:-(len(".tar.gz"))]
        identifier = basename.replace("+", " ")

        self.path = os.path.join(root_directory, "snapshots", identifier)
        self._identifier = identifier
        self._contents_path = os.path.join(self.path, "contents.tar.gz")
        self._metadata_path = os.path.join(self.path, "metadata.json")
        self._metadata = None

    def sync(self):
        logging.info("Syncing '%s'...", self.url)
        if os.path.exists(self.path):
            return
        with tempfile.TemporaryDirectory() as temporary_directory, contextlib.chdir(temporary_directory):
            print("Creating directory...")
            filename = utils.download_file(self.url)
            contents_path = os.path.join(temporary_directory, "contents")
            os.makedirs(contents_path)
            containers.extract_tar_gz(filename, contents_path)
            shutil.move(contents_path, self.path)

    @property
    def metadata(self):
        if self._metadata is None:
            with open(self._metadata_path) as fh:
                self._metadata = json.load(fh)
        return self._metadata

    @property
    def title(self):
        return self.metadata['title']

    @property
    def snapshot_url(self):
        return self.metadata["url"]

    @property
    def description(self):
        return ""

    @property
    def assets(self):

        source_reference = model.ReferenceItem(name=self.title, url=self.snapshot_url)

        def make_link(reference):
            return model.ReferenceItem(name=reference.name, url=self.snapshot_url + "/" + reference.name)

        def resolve_reference(reference):
            contents_reference = reference[1:]
            if len(contents_reference) < 1:
                return [source_reference]
            else:
                return [source_reference] + [make_link(contents_reference[0])] + contents_reference[1:]

        for path, reference in containers.walk(self._contents_path, relative_to=self.path):
            yield path, resolve_reference(reference)

    def as_dict(self):
        return {
            "name": self.title,
            "html_url": self.snapshot_url,
        }
