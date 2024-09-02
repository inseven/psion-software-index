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
import tempfile
import zipfile

import pycdlib

import model


def _extract_iso(path, destination_path):

    iso = pycdlib.PyCdlib()
    iso.open(path)

    pathname = 'joliet_path'
    start_path = '/'
    root_entry = iso.get_record(**{pathname: start_path})

    dirs = collections.deque([root_entry])
    while dirs:
        dir_record = dirs.popleft()
        ident_to_here = iso.full_path_from_dirrecord(dir_record,
                                                     rockridge=pathname == 'rr_path')
        relname = ident_to_here[len(start_path):]
        if relname and relname[0] == '/':
            relname = relname[1:]
        if dir_record.is_dir():
            if relname != '':
                os.makedirs(os.path.join(destination_path, relname))
            child_lister = iso.list_children(**{pathname: ident_to_here})

            for child in child_lister:
                if child is None or child.is_dot() or child.is_dotdot():
                    continue
                dirs.append(child)
        else:
            if dir_record.is_symlink():
                fullpath = os.path.join(destination_path, relname)
                local_dir = os.path.dirname(fullpath)
                local_link_name = os.path.basename(fullpath)
                old_dir = os.getcwd()
                os.chdir(local_dir)
                os.symlink(dir_record.rock_ridge.symlink_path(), local_link_name)
                os.chdir(old_dir)
            else:
                iso.get_file_from_iso(os.path.join(destination_path, relname), **{pathname: ident_to_here})


class Iso(object):

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.temporary_directory = tempfile.TemporaryDirectory()

    def __enter__(self):
        self.pwd = os.getcwd()
        self.temporary_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temporary_directory.name)
        _extract_iso(self.path, self.temporary_directory.name)
        return self.temporary_directory.name

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.pwd)
        self.temporary_directory.cleanup()


class Zip(object):

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.temporary_directory = tempfile.TemporaryDirectory()

    def __enter__(self):
        self.pwd = os.getcwd()
        self.temporary_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temporary_directory.name)
        try:
            with zipfile.ZipFile(self.path) as zip:
                zip.extractall()
            return self.temporary_directory.name
        except:
            os.chdir(self.pwd)
            self.temporary_directory.cleanup()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.pwd)
        self.temporary_directory.cleanup()


CONTAINER_MAPPING = {
    ".bin": Iso,
    ".iso": Iso,
    ".zip": Zip,
}

def walk(path, reference=None, relative_to=None):
    reference = reference if reference is not None else []
    path = os.path.abspath(path)
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            for a in [os.path.join(root, f) for f in files]:
                reference_item = model.ReferenceItem(name=os.path.relpath(a, relative_to), url=None)
                for (inner_path, inner_reference) in walk(a, reference=reference + [reference_item]):
                    yield (inner_path, inner_reference)
    else:
        reference_item = model.ReferenceItem(name=os.path.relpath(path, relative_to), url=None)
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        if ext in CONTAINER_MAPPING:
            logging.debug("Extracting '%s'...", path)
            try:
                with CONTAINER_MAPPING[ext](path) as contents_path:
                    for (inner_path, inner_reference) in walk(contents_path,
                                                              reference=reference + [reference_item],
                                                              relative_to=contents_path):
                        yield (inner_path, inner_reference)
            except NotImplementedError as e:
                logging.warning("Unsupported zip file '%s', %s.", path, e)
            except zipfile.BadZipFile as e:
                logging.warning("Corrupt zip file '%s', %s.", path, e)
        else:
            yield (path, reference)