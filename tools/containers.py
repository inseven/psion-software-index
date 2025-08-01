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

import collections
import logging
import os
import subprocess
import tarfile
import tempfile
import zipfile
import zlib

import model


def extract_7z(source, destination):
    subprocess.check_call(["7z", "-o%s" % destination, "x", source])


def extract_tar(source, destination):
    with tarfile.TarFile(source) as tar:
        tar.extractall(path=destination)


def extract_tar_gz(source, destination):
    subprocess.check_call(["tar", "-zxvf", source, "-C", destination])


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


def get_extraction_method(path):
    for ext, extraction_method in CONTAINER_MAPPING.items():
        if path.lower().endswith(ext):
            return extraction_method
    return None


class Extractor(object):

    def __init__(self, path, method):
        self.path = os.path.abspath(path)
        self.method = method

    def __enter__(self):
        self.pwd = os.getcwd()
        self.temporary_directory = tempfile.TemporaryDirectory()  # TODO: Redundant?
        os.chdir(self.temporary_directory.name)
        try:
            self.method(self.path, self.temporary_directory.name)
            return self.temporary_directory.name
        except:
            os.chdir(self.pwd)
            self.temporary_directory.cleanup()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.pwd)
        self.temporary_directory.cleanup()


def walk(path, reference=None, relative_to=None):
    reference = reference if reference is not None else []
    path = os.path.abspath(path)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            files = [f for f in files if not f.startswith("._")]  # Ignore resource files.
            for a in [os.path.join(root, f) for f in files]:
                reference_item = model.ReferenceItem(name=os.path.relpath(a, relative_to), url=None)
                for (inner_path, inner_reference) in walk(a, reference=reference, relative_to=relative_to):
                    yield (inner_path, inner_reference)
    else:
        reference_item = model.ReferenceItem(name=os.path.relpath(path, relative_to), url=None)
        extraction_method = get_extraction_method(path)
        if extraction_method is not None:
            logging.debug("Extracting '%s'...", path)
            try:
                with Extractor(path, method=extraction_method) as contents_path:
                    for (inner_path, inner_reference) in walk(contents_path,
                                                              reference=reference + [reference_item],
                                                              relative_to=contents_path):
                        yield (inner_path, inner_reference)
            except (NotImplementedError,
                    zipfile.BadZipFile,
                    OSError, RuntimeError,
                    tarfile.ReadError,
                    zlib.error,
                    subprocess.CalledProcessError) as e:
                logging.warning("Failed to extract file '%s' with error '%s'.", path, e)
        else:
            yield (path, reference + [reference_item])
