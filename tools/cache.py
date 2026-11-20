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
import hashlib
import os
import pathlib


_SCRIPT_PATH = os.path.abspath(__file__)


def _digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _get_identifier(*components):
    h = hashlib.sha256()
    for component in components:
        h.update(component.encode('utf-8'))
    return h.hexdigest()


@contextlib.contextmanager
def disk_cache(directory, key):
    cache_directory = os.path.join(os.path.abspath(directory), _get_identifier(_digest(_SCRIPT_PATH), key))
    contents_directory = os.path.join(cache_directory, "contents")
    marker_path = os.path.join(cache_directory, "CACHE")
    os.makedirs(contents_directory, exist_ok=True)
    try:
        yield contents_directory
    finally:
        pathlib.Path(marker_path).touch()
