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
import array
import base64
import collections
import contextlib
import copy
import csv
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import urllib.parse

from enum import Enum

import frontmatter
import natsort

from PIL import Image as PILImage, ImageOps

import common
import containers
import model
import opolua
import utils

TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)

verbose = '--verbose' in sys.argv[1:] or '-v' in sys.argv[1:]
logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="[%(levelname)s] %(message)s")


# TODO: Check if there are more languages.
LANGUAGE_ORDER = ["en_GB", "en_US", "en_AU", "fr_FR", "de_DE", "it_IT", "nl_NL", "bg_BG", ""]


class MissingName(Exception):
    pass


class ReleaseKind(Enum):
    INSTALLER = "installer"
    STANDALONE = "standalone"

class Chdir(object):

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.pwd = os.getcwd()
        os.chdir(self.path)
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.pwd)


class DummyMetadataProvider(object):

    def summary_for(self, path):
        return None


class Summary(object):

    def __init__(self, installer_count, uid_count, version_count, sha_count):
        self.installer_count = installer_count
        self.uid_count = uid_count
        self.version_count = version_count
        self.sha_count = sha_count

    def as_dict(self):
        return {
            'installerCount': self.installer_count,
            'uidCount': self.uid_count,
            'versionCount': self.version_count,
            'shaCount': self.sha_count,
        }


class Version(object):

    def __init__(self, installers):
        self.installers = installers
        self.variants = group_collections(installers, lambda x: x['sha256'])

    @property
    def version(self):
        return self.installers[0]['version']

    def as_dict(self):
        # TODO: We probably don't want to do this in the future, but for the time being, we strip some data out of the
        # releases to make sure they exactly match the original format to avoid making too many changes at once.
        variants = [{
            'identifier': variant.identifier,
            'items': copy.deepcopy(variant.items),
        } for variant in self.variants]

        for variant in variants:
            for item in variant['items']:
                if 'icon' in item and 'bpp' in item['icon']:
                    del item['icon']['bpp']

        return {
            'version': self.version,
            'variants': variants,
        }


class Program(object):

    def __init__(self, uid, installers, screenshots):
        self.uid = uid
        self.installers = installers  # TODO: Item / Program / Release?
        self.screenshots = screenshots
        versions = collections.defaultdict(list)
        for installer in installers:
            versions[installer['version']].append(installer)
        # We use `natsort` to sort the versions to ensure, for example, 10.0 sorts _after_ 2.0.
        self.versions = natsort.natsorted([Version(installers=installers) for installers in versions.values()], key=lambda x: x.version)
        tags = set()
        for installer in installers:
            for tag in installer['tags']:
                tags.add(tag)
        self.tags = tags
        kinds = set()
        for installer in installers:
            kinds.add(installer['kind'])
        self.kinds = kinds


    @property
    def name(self):
        return self.installers[0]['name']

    @property
    def summary(self):
        # TODO: Maybe select the first non-empty one (see readme).
        if 'summary' not in self.installers[0]:
            return None
        return self.installers[0]['summary']

    @property
    def icon(self):
        return select_icon_dict([installer['icon'] for installer in self.installers
                                if 'icon' in installer])

    def as_dict(self):
        dict = {
            'uid': self.uid,
            'name': self.name,
            'summary': self.summary,
            'versions': [version.as_dict() for version in self.versions],
            'tags': sorted(list(self.tags)),
            'kinds': [kind for kind in self.kinds],
        }
        summary = self.summary
        if summary:
            dict['summary'] = summary
        icon = self.icon
        if icon:
            dict['icon'] = icon
            # TODO: Don't recreate the dict.
            dict['icon'] = {
                'path': icon['path'],
                'width': icon['width'],
                'height': icon['height'],
            }
        return dict


class Release(object):

    # TODO: Make the UID optional and don't attempt to synthesize other identifiers at this stage.
    def __init__(self, filename, size, reference, kind, identifier, sha256, name, version, icons, tags):
        self.filename = filename
        self.size = size
        self.reference = reference
        self.kind = kind
        self.uid = identifier
        self.sha256 = sha256
        self.name = name
        self.version = version
        self.icons = icons
        self.tags = tags

    def as_dict(self, relative_icons_path):
        dict = {
            'filename': self.filename,
            'size': self.size,
            'reference': [item.as_dict() for item in self.reference],
            'kind': self.kind.value,
            'sha256': self.sha256,
            'uid': self.uid,
            'name': self.name,
            'version': self.version,
            'tags': sorted(list(self.tags)),
        }
        dict['icons'] = [{'filename': icon.filename,
                          'width': icon.width,
                          'height': icon.height,
                          'bpp': icon.bpp,
                          'sha256': icon.shasum} for icon in self.icons]
        return dict

    def write_assets(self, icons_path):
        for icon in self.icons:
            icon.write(directory_path=icons_path)


class Reference(object):

    def __init__(self, parent, path):
        self.parent = parent
        self.path = path

    def __str__(self):
        return os.path.join(self.parent.path, self.path)


def decode(s, encodings=('ascii', 'utf8', 'latin1', 'cp1252')):
    for encoding in encodings:
        try:
            return s.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("Unknown encoding")


def find_sibling(path, name):
    directory_path = os.path.dirname(path)
    files = os.listdir(directory_path)
    for f in files:
        if f.lower() == name.lower():
            return os.path.join(directory_path, f)


def select_icon_dict(icons):
    candidates = [icon for icon in icons if icon['width'] == icon['height'] and icon['width'] <= 48]
    icons = list(reversed(sorted(candidates, key=lambda x: (x['bpp'], x['width']))))
    if len(icons) < 1:
        return None
    return icons[0]


def group_collections(installers, group_by):
    groups = collections.defaultdict(list)
    for installer in installers:
        groups[group_by(installer)].append(installer)
    return [model.Collection(identifier, installers) for identifier, installers in groups.items()]


def select_name(names):
    for language in LANGUAGE_ORDER:
        if language in names:
            return names[language]
    logging.error("Failed to select a name from candidates '%s'.", names)
    raise MissingName("No supported localizations found")


def shasum(path):
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()


TAG_MAPPING = {
    "opl": "opl",
    "opo": "opl",
    "opa": "opl",
    "er5": "epoc32",
}


def remap_tag(tag):
    try:
        return TAG_MAPPING[tag]
    except KeyError:
        return tag


def discover_tags(path):
    tags = set([])
    with Chdir(path):
        for f in glob.glob("**/*", recursive=True):
            if os.path.isdir(f):
                continue
            details = opolua.recognize(f)
            if "era" in details:
                tags.add(remap_tag(details["era"]))
            if "type" in details:
                tags.add(remap_tag(details["type"]))
    if "unknown" in tags:
        tags.remove("unknown")
    return tags


def import_installer(source, output_directory, reference, path, error_handler):
    info = opolua.dumpsis(path)
    icons = []
    tags = []

    # TODO: Move this into an OpoLua utility.
    with tempfile.TemporaryDirectory() as temporary_directory_path:

        with Chdir(temporary_directory_path):
            opolua.dumpsis_extract(path, temporary_directory_path)

            tags = discover_tags(temporary_directory_path)

            contents = glob.glob("**/*.aif", recursive=True)
            if contents:
                aif_path = contents[0]
                try:
                    icons = opolua.get_icons(aif_path)
                except Exception as e:
                    error_handler(aif_path, e)

    sha256 = shasum(path)
    shutil.copyfile(path, os.path.join(output_directory, sha256))
    return Release(filename=os.path.basename(path),
                   size=os.path.getsize(path),
                   reference=reference,
                   kind=ReleaseKind.INSTALLER,
                   identifier="0x%08x" % info["uid"],
                   sha256=sha256,
                   name=select_name(info["name"]),
                   version=info["version"],
                   icons=icons,
                   tags=tags)


# TODO: Rename to just import?
def import_source(source, output_directory, error_handler=None):

    apps = []
    logging.info(f"Importing source '{source.path}'...")
    for (file_path, reference) in source.assets:
        basename = os.path.basename(file_path)
        name, ext = os.path.splitext(basename)
        ext = ext.lower()

        if ext == ".app" or ext == ".opa":

            # TODO: Combine APP and SIS.

            tags = discover_tags(os.path.dirname(file_path))

            logging.info(f"Importing app '{file_path}'...")
            aif_path = find_sibling(file_path, name + ".aif")
            uid = shasum(file_path)
            icons = []
            app_name = name
            if aif_path:
                try:
                    info = opolua.dumpaif(aif_path)
                    uid = ("0x%08x" % info["uid3"]).lower()
                    app_name = select_name(info["captions"])
                    icons = opolua.get_icons(aif_path)
                except MissingName as e:
                    error_handler(aif_path, e)
                except BaseException as e:
                    error_handler(aif_path, e)
                    logging.warning("Failed to parse APP as AIF with message '%s'", e)
            else:
                try:
                    info = opolua.dumpaif(file_path)
                    icons = opolua.get_icons(file_path)
                    app_name = select_name(info["captions"])
                except opolua.InvalidAIF as e:
                    error_handler(file_path, e)
                except BaseException as e:
                    error_handler(file_path, e)
                    logging.warning("Failed to parse APP as AIF with message '%s'", e)
            sha256 = shasum(file_path)
            shutil.copyfile(file_path, os.path.join(output_directory, sha256))
            release = Release(filename=os.path.basename(file_path),
                              size=os.path.getsize(file_path),
                              reference=reference,
                              kind=ReleaseKind.STANDALONE,
                              identifier=uid,
                              sha256=sha256,
                              name=app_name,
                              version="Unknown",
                              icons=icons,
                              tags=tags)
            apps.append(release)

        elif ext == ".sis":

            logging.info(f"Importing installer '{file_path}'...")
            try:
                apps.append(import_installer(source=source,
                                             output_directory=output_directory,
                                             reference=reference,
                                             path=file_path,
                                             error_handler=error_handler))
            except opolua.InvalidInstaller as e:
                logging.error("Failed to import installer with message '%s", e)
                error_handler(file_path, e)
            except Exception as e:
                logging.error("Failed to import installer with message '%s", e)
                error_handler(file_path, e)

    return apps


def index(library):

    # Paths.
    # TODO: These are shared between different indexing stages and should probably be a property of the library itself.
    releases_path = os.path.join(library.intermediates_directory, "releases.json")
    files_directory = os.path.join(library.intermediates_directory, "files")
    icons_directory = os.path.join(library.intermediates_directory, "icons")
    errors_directory = os.path.join(library.intermediates_directory, "errors")

    # Clean up the intermediates directory.
    if os.path.exists(library.intermediates_directory):
        shutil.rmtree(library.intermediates_directory)
    os.makedirs(library.intermediates_directory)
    os.makedirs(files_directory)
    os.makedirs(icons_directory)
    os.makedirs(errors_directory)

    # Capture failing files for later investigation.
    # This creates a new path for each unique failing file and stores the error alongside the file.
    def error_handler(path, error):
        sha = shasum(path)
        destination_path = os.path.join(errors_directory, sha)
        if os.path.exists(destination_path):
            logging.warning(f"Ignoring duplicate failing file with shasum '{sha}'...")
            return
        os.makedirs(destination_path)
        shutil.copy(path, destination_path)
        with open(os.path.join(destination_path, "error.txt"), "w") as fh:
            fh.write(str(error))

    # Index all the individual releases.
    logging.info("Indexing...")
    releases = []
    for source in library.sources:
        releases += import_source(source=source,
                                  output_directory=files_directory,
                                  error_handler=error_handler)

    # Write out the icons.
    logging.info("Writing icons to '%s'...", icons_directory)
    for release in releases:
        release.write_assets(icons_directory)

    # Write the intermediate index.
    logging.info("Writing intermediate index to '%s'...", releases_path)
    with open(releases_path, "w") as fh:
        json.dump([release.as_dict(relative_icons_path="icons") for release in releases], fh, indent=4)

    logging.info("Indexing complete.")


def group(library):
    # TODO: Surely this should be a property of the library!!
    summary_path = os.path.join(library.index_directory, "summary.json")
    sources_path = os.path.join(library.index_directory, "sources.json")
    programs_path = os.path.join(library.index_directory, "programs.json")
    group_index_path = os.path.join(library.index_directory, "groups.json")
    files_path = os.path.join(library.index_directory, "files")
    icons_path = os.path.join(library.index_directory, "icons")

    # TODO: Move into library.
    releases_path = os.path.join(library.intermediates_directory, "releases.json")
    intermediate_files_directory = os.path.join(library.intermediates_directory, "files")
    intermediate_icons_directory = os.path.join(library.intermediates_directory, "icons")

    # Load the releases.
    with open(releases_path) as fh:
        releases = json.load(fh)

    # Generate the library summary.
    unique_uids = set()
    unique_versions = set()
    unique_shas = set()
    total_count = 0
    details = collections.defaultdict(list)
    groups = collections.defaultdict(list)

    for release in releases:
        unique_uids.add(release['uid'])
        unique_versions.add((release['uid'], release['version']))
        unique_shas.add(release['sha256'])
        total_count = total_count + 1
        details[(release['uid'], release['sha256'], release['version'])].append(release)
        groups[(release['uid'])].append(release)
    summary = Summary(installer_count=total_count,
                      uid_count=len(unique_uids),
                      version_count=len(unique_versions),
                      sha_count=len(unique_shas))

    # Generate the library by grouping the programs together by identifier/uid.
    # This relies heavily on automatic grouping in the `Program` constructor which we may wish to make more explicit in
    # the future.
    programs = []
    for identifier, installers in sorted([item for item in groups.items()],
                                         key=lambda x: x[1][0]['name'].lower()):

        releases = []
        for installer in installers:
            # Strip down the release for the API.
            required_keys = ['filename', 'size', 'reference', 'kind', 'sha256', 'uid', 'name', 'version', 'tags']
            release = {}
            for key in required_keys:
                release[key] = installer[key]
            icon = select_icon_dict(installer['icons'])
            if icon is not None:
                release['icon'] = {
                    'path': os.path.join("icons", icon['filename']),
                    'width': icon['width'],
                    'height': icon['height'],
                    'bpp': icon['bpp'],
                }
            releases.append(release)

        programs.append(Program(identifier, releases, []))

    # Generate a minimal grouped index to use for search and filtering.
    group_index = []
    for program in programs:
        entry = {
            'uid': program.uid,
            'name': program.name,
        }
        if program.icon is not None:
            entry['icon'] = program.icon
        group_index.append(entry)

    # Create the output directory.
    os.makedirs(library.index_directory, exist_ok=True)

    # Write the summary.
    logging.info("Writing summary to '%s'...", summary_path)
    with open(summary_path, "w") as fh:
        json.dump(summary.as_dict(), fh)

    # Write the sources.
    logging.info("Writing sources to '%s'...", sources_path)
    with open(sources_path, "w") as fh:
        json.dump([source.as_dict() for source in library.sources], fh)

    # Write the library.
    logging.info("Writing library to '%s'...", programs_path)
    with open(programs_path, "w", encoding="utf-8") as fh:
        json.dump([program.as_dict() for program in programs], fh)

    # Write the group index.
    logging.info("Writing group index to '%s'...", group_index_path)
    with open(group_index_path, "w", encoding="utf-8") as fh:
        json.dump(group_index, fh)



    # Copy the files.
    logging.info("Copying files to '%s'...", files_path)
    if os.path.exists(files_path):
        shutil.rmtree(files_path)
    shutil.copytree(intermediate_files_directory, files_path)

    # Copy the icons.
    logging.info("Copying icons to '%s'...", icons_path)
    if os.path.exists(icons_path):
        shutil.rmtree(icons_path)
    shutil.copytree(intermediate_icons_directory, icons_path)


def overlay(library):
    logging.info("Applying overlay...")

    source_programs_path = os.path.join(library.index_directory, "programs.json")
    source_sources_path = os.path.join(library.index_directory, "sources.json")
    source_summary_path = os.path.join(library.index_directory, "summary.json")
    source_group_index_path = os.path.join(library.index_directory, "groups.json")
    files_path = os.path.join(library.index_directory, "files")
    icons_path = os.path.join(library.index_directory, "icons")

    data_output_path = os.path.join(library.output_directory, "_data")
    screenshots_output_path = os.path.join(library.output_directory, "screenshots")
    files_output_path = os.path.join(library.output_directory, "files")
    icons_output_path = os.path.join(library.output_directory, "icons")
    api_v1_output_path = os.path.join(library.output_directory, "api", "v1")

    destination_programs_path = os.path.join(data_output_path, "programs.json")
    destination_sources_path = os.path.join(data_output_path, "sources.json")
    destination_summary_path = os.path.join(data_output_path, "summary.json")
    destination_group_index_path = os.path.join(data_output_path, "groups.json")

    # Import screenshots and metadata from the overlay.
    overlay = collections.defaultdict(dict)
    for overlay_directory in library.overlay_directories:
        for identifier in os.listdir(overlay_directory):
            if identifier.startswith("."):
                continue
            screenshots_path = os.path.join(overlay_directory, identifier)
            overlay[identifier]["screenshots"] = [os.path.join(screenshots_path, screenshot)
                                                  for screenshot in os.listdir(screenshots_path)
                                                  if screenshot.endswith(".png")]
            overlay_index_path = os.path.join(overlay_directory, identifier, "index.md")
            if os.path.exists(overlay_index_path):
                overlay[identifier]["index"] = frontmatter.load(overlay_index_path)

    # Load the index.
    with open(source_programs_path) as fh:
        index = json.load(fh)

    # Clean up the destination paths.
    if os.path.exists(screenshots_output_path):
        shutil.rmtree(screenshots_output_path)
    if os.path.exists(data_output_path):
        shutil.rmtree(data_output_path)
    if os.path.exists(files_output_path):
        shutil.rmtree(files_output_path)
    if os.path.exists(icons_output_path):
        shutil.rmtree(icons_output_path)
    if os.path.exists(api_v1_output_path):
        shutil.rmtree(api_v1_output_path)

    # Create the output directories if they don't exist.
    os.makedirs(data_output_path, exist_ok=True)
    os.makedirs(screenshots_output_path, exist_ok=True)

    # Merge the overlay into the index.
    for application in index:
        identifier = application['uid']
        if identifier not in overlay:
            continue

        # Inject the metadata.
        if "index" in overlay[identifier]:
            metadata = overlay[identifier]["index"]
            application['description'] = metadata.content
            for key in metadata.metadata.keys():
                application[key] = metadata.metadata[key]

        # Inject the screenshots.
        screenshots = overlay[identifier]["screenshots"] if "screenshots" in overlay[identifier] else []
        os.makedirs(os.path.join(screenshots_output_path, identifier))
        relative_paths = []
        for screenshot in sorted(screenshots):
            relative_path = os.path.join("screenshots", identifier, os.path.basename(screenshot))
            destination_path = os.path.join(library.output_directory, relative_path)
            logging.info("Copying '%s' to '%s'...", screenshot, destination_path)
            shutil.copyfile(screenshot, destination_path)
            with PILImage.open(screenshot) as image:
                width, height = image.size
            relative_paths.append({
                "width": width,
                "height": height,
                "path": relative_path,
            })
        application['screenshots'] = relative_paths

    # Write the index.
    shutil.copyfile(source_sources_path, destination_sources_path)
    shutil.copyfile(source_summary_path, destination_summary_path)
    shutil.copyfile(source_group_index_path, destination_group_index_path)
    with open(destination_programs_path, "w") as fh:
        json.dump(index, fh)

    # Copy the files.
    shutil.copytree(files_path, files_output_path)

    # Copy the icons.
    shutil.copytree(icons_path, icons_output_path)

    # Copy the API.
    os.makedirs(api_v1_output_path, exist_ok=True)
    shutil.copytree(icons_output_path, os.path.join(api_v1_output_path, "icons"))
    shutil.copytree(screenshots_output_path, os.path.join(api_v1_output_path, "screenshots"))
    os.makedirs(os.path.join(api_v1_output_path, "programs"), exist_ok=True)
    shutil.copyfile(destination_programs_path, os.path.join(api_v1_output_path, "programs", "index.json"))
    os.makedirs(os.path.join(api_v1_output_path, "sources"), exist_ok=True)
    shutil.copyfile(destination_sources_path, os.path.join(api_v1_output_path, "sources", "index.json"))
    os.makedirs(os.path.join(api_v1_output_path, "summary"), exist_ok=True)
    shutil.copyfile(destination_summary_path, os.path.join(api_v1_output_path, "summary", "index.json"))
    os.makedirs(os.path.join(api_v1_output_path, "groups"), exist_ok=True)
    shutil.copyfile(destination_group_index_path, os.path.join(api_v1_output_path, "groups", "index.json"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("definition")
    parser.add_argument("command", choices=["sync", "index", "group", "overlay"], nargs="+", help="command to run")
    parser.add_argument('--verbose', '-v', action='store_true', default=False, help="show verbose output")
    options = parser.parse_args()

    library = common.Library(options.definition)

    for command in options.command:
        if command == "sync":
            library.sync()
        if command == "index":
            index(library)
        if command == "group":
            group(library)
        if command == "overlay":
            overlay(library)


if __name__ == "__main__":
    main()
