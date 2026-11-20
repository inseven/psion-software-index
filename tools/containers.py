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

import collections
import contextlib
import enum
import errno
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
import zlib

from . import cache
from . import model
from . import utils


SEVEN_ZIP_COMMAND = "7zz"


class MissingTool(Exception):
    pass


class ItemType(enum.Enum):
    FILE = 1
    DIRECTORY = 2
    CONTAINER = 3
    LIBRARY = 4


class Item(object):

    def __init__(self, type, name, identifier, children):
        self.type = type
        self.name = name
        self.identifier = identifier
        self.children = children

    def get_extension(self):
        _, ext = os.path.splitext(self.name)
        return ext.lower()


def run_command(command):
    """
    Brittle convenience for running commands that attempts to provide slightly more nuanced exceptions by detecting
    certain OS errors in stderr by performing a string comparison against the standard OS output.
    """
    result = subprocess.run(command, stderr=subprocess.PIPE)
    stderr = result.stderr.decode("utf-8", errors="replace")
    sys.stderr.write(stderr)
    if result.returncode != 0:
        for error_number in [errno.ENOSPC, errno.EDQUOT]:
            if os.strerror(error_number) in stderr:
                raise OSError(error_number, os.strerror(error_number), command[0])
        raise subprocess.CalledProcessError(result.returncode, command, stderr=result.stderr)


def extract_7z(source, destination):
    seven_zip_path = shutil.which(SEVEN_ZIP_COMMAND)
    if seven_zip_path is None:
        raise MissingTool(f"Unable to find '{SEVEN_ZIP_COMMAND}'.")
    run_command([seven_zip_path, "-o%s" % destination, "x", source])


def extract_tar(source, destination):
    with tarfile.TarFile(source) as tar:
        tar.extractall(path=destination)


def extract_tar_gz(source, destination):
    run_command(["tar", "-zxvf", source, "-C", destination])


def extract_zip(source, destination):
    with zipfile.ZipFile(source) as zip:
        zip.extractall(path=destination)


CONTAINER_MAPPING = {
    ".7z": extract_7z,
    ".cab": extract_7z,
    ".ima": extract_7z,
    ".iso": extract_7z,
    ".tar.gz": extract_tar_gz,
    ".tar": extract_tar,
    ".tgz": extract_tar_gz,
    ".zip": extract_zip,
    ".vhd": extract_7z,
}


def get_extractor(path):
    for ext, extraction_method in CONTAINER_MAPPING.items():
        if path.lower().endswith(ext):
            return Extractor(path, extraction_method)
    return None


class UnsupportedContainer(Exception):
    pass


class ExtractionCache(object):

    def __init__(self, cache_directory):
        self._cache_directory = cache_directory
        self._cache_key = utils.shasum(__file__)
        self._lock = threading.Lock()

    def extract(self, path):
        return self.extractor(path)

    def extractor(self, path):
        extractor = get_extractor(path)
        if extractor is None:
            return None

        @contextlib.contextmanager
        def caching_extractor():
            path_sha = utils.shasum(path)
            with cache.disk_cache(self._cache_directory, f"{self._cache_key}_{path_sha}") as directory:
                extraction_directory = os.path.join(directory, "contents")
                with self._lock:
                    if not os.path.exists(extraction_directory):
                        with extractor as snapshot_path:
                            shutil.move(snapshot_path, extraction_directory)
                yield extraction_directory

        return caching_extractor()


class Extractor(object):

    def __init__(self, path, method):
        self.path = os.path.abspath(path)
        self.method = method

    def __enter__(self):
        self.pwd = os.getcwd()
        self.temporary_directory = tempfile.TemporaryDirectory()
        try:
            self.method(self.path, self.temporary_directory.name)
            return self.temporary_directory.name
        except (NotImplementedError,
                zipfile.BadZipFile,
                OSError,
                RuntimeError,
                tarfile.ReadError,
                zlib.error,
                subprocess.CalledProcessError) as e:
            self.temporary_directory.cleanup()
            if isinstance(e, OSError) and e.errno in [errno.ENOSPC, errno.EDQUOT]:
                # Propagate fatal OS errors.
                raise
            raise UnsupportedContainer(self.path)
        except:
            self.temporary_directory.cleanup()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.temporary_directory.cleanup()


def get_child_items(path, cache_path):
    return [get_contents(os.path.join(path, file), cache_path)
            for file in os.listdir(path)
            if not file.startswith(".")]


def get_contents(path, cache_path):
    path = os.path.abspath(path)

    # First check for regular directories.
    if os.path.isdir(path):
        return Item(type=ItemType.DIRECTORY,
                    name=os.path.basename(path),
                    identifier=None,
                    children=get_child_items(path, cache_path))

    # Next try indexing known containers.
    extractor = get_extractor(path)
    identifier = utils.shasum(path)
    name = os.path.basename(path)
    shutil.copyfile(path, os.path.join(cache_path, identifier))
    if extractor is not None:
        try:
            with extractor as container_path:
                children = get_child_items(container_path, cache_path)
                return Item(type=ItemType.CONTAINER,
                            name=name,
                            identifier=identifier,
                            children=children)
        except UnsupportedContainer as e:
            logging.warning("Failed to extract file '%s' with error '%s'.", path, e)

    # Finally, treat it as a regular file.
    return Item(type=ItemType.FILE,
                name=name,
                identifier=identifier,
                children=[])


def walk(cache, path, reference=None, relative_to=None):
    reference = reference if reference is not None else []
    path = os.path.abspath(path)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            files = [f for f in files if not f.startswith("._")]  # Ignore resource files.
            for a in [os.path.join(root, f) for f in files]:
                reference_item = model.ReferenceItem(name=os.path.relpath(a, relative_to), url=None)
                for (inner_path, inner_reference) in walk(cache, a, reference=reference, relative_to=relative_to):
                    yield (inner_path, inner_reference)
    else:
        reference_item = model.ReferenceItem(name=os.path.relpath(path, relative_to), url=None)
        extractor = cache.extractor(path)
        if extractor is not None:
            logging.debug("Extracting '%s'...", path)
            try:
                with extractor as contents_path:
                    for (inner_path, inner_reference) in walk(cache,
                                                              contents_path,
                                                              reference=reference + [reference_item],
                                                              relative_to=contents_path):
                        yield (inner_path, inner_reference)
            except UnsupportedContainer as e:
                logging.warning("Failed to extract file '%s' with error '%s'.", path, e)
        else:
            yield (path, reference + [reference_item])
