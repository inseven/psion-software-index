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

import hashlib
import logging
import os
import requests
import shutil
import tempfile

from dataclasses import dataclass

import xml.etree.ElementTree as ET

from tqdm import tqdm


@dataclass
class InternetArchiveMetdata:
    identifier: str
    title: str
    description: str

    @classmethod
    def loads(cls, contents):
        root = ET.fromstring(contents)
        return cls(identifier=root.find('./identifier').text,
                   title=root.find('./title').text,
                   description=root.find('./description').text)

    @classmethod
    def load(cls, fh):
        root = ET.fromstring(fh.read())
        return cls(identifier=root.find('./identifier').text,
                   title=root.find('./title').text,
                   description=root.find('./description').text)

    @classmethod
    def get(cls, identifier):
        """
        Download the Internet Archive metadata for item `identifier`.
        """
        response = requests.get(f"https://archive.org/download/{identifier}/{identifier}_meta.xml")
        return cls.loads(response.text)


@dataclass
class InternetArchiveFile:
    name: str
    source: str
    format: str
    size: int | None
    md5: str | None
    sha1: str | None

    @classmethod
    def from_element(cls, element):
        size_element = element.find('size')
        md5_element = element.find('md5')
        sha1_element = element.find('sha1')
        return cls(name=element.get('name'),
                   source=element.get('source'),
                   format=element.find('./format').text,
                   size=size_element.text if size_element is not None else None,
                   md5=md5_element.text if md5_element is not None else None,
                   sha1=sha1_element.text if sha1_element is not None else None)


@dataclass
class InternetArchiveFiles:
    files: [InternetArchiveFile]

    @classmethod
    def loads(cls, contents):
        root = ET.fromstring(contents)
        return cls(files=[InternetArchiveFile.from_element(f) for f in root.findall('./file')])

    @classmethod
    def load(cls, fh):
        return cls.loads(fh.read())

    @classmethod
    def get(cls, identifier):
        """
        Download the Internet Archive file listing for item `identifier`.
        """
        response = requests.get(f"https://archive.org/download/{identifier}/{identifier}_files.xml")
        return cls.loads(response.text)


def format_version(version):
    return "%d.%02d" % (version['major'], version['minor'])


def reset_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)


def create_directories(paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)


def listdir(path, include_hidden):
    return [f for f in os.listdir(path) if (include_hidden or not f.startswith("."))]


def digest(*paths, method):
    h = method()
    for path in paths:
        if os.path.isdir(path):
            for f in sorted(listdir(path, include_hidden=False)):
                h.update(shasum(os.path.join(path, f)).encode('utf-8'))
        else:
            with open(path, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    h.update(data)
    return h.hexdigest()


def shasum(*paths):
    return digest(*paths, method=hashlib.sha256)


def merge_files(source, destination):
    for f in listdir(source, include_hidden=False):
        source_path = os.path.join(source, f)
        destination_path = os.path.join(destination, f)
        if not os.path.exists(destination_path):
            shutil.copy(source_path, destination_path)


def safe_identifier(id):
    return id.replace(".", "-").replace(" ", "+").replace("/", "-").replace(":", "-")


def download_file(url, local_filename=None):
    logging.info("Downloading '%s'...", url)
    local_filename = local_filename if local_filename is not None else url.split('/')[-1]
    basename = os.path.basename(local_filename)
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = os.path.join(temporary_directory, basename)
            total_size = int(response.headers.get("content-length", 0))
            with tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
                with open(temporary_path, 'wb') as fh:
                    for data in response.iter_content(chunk_size=1024 * 1024):
                        progress_bar.update(len(data))
                        fh.write(data)
                shutil.move(temporary_path, local_filename)

    return local_filename
