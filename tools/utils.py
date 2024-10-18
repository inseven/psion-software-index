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

import logging
import os
import requests
import shutil
import tempfile

from tqdm import tqdm


def download_file_with_mirrors(urls, local_filename=None):
    urls = list(urls)
    while True:
        url = urls.pop(0)
        try:
            return download_file(url, local_filename)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 503 or len(urls) < 1:
                raise
            continue
        except requests.exceptions.ConnectTimeout:
            if len(urls) < 1:
                raise
            continue


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
