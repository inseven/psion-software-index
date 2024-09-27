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


# These SIS files currently cause issues with the extraction tools we're using so they're being ignored for the time
# being to allow us to make progress with some of the existing libraries.
IGNORED = set([
    "netutils.sis",
    "NETUTILS.SIS",
    "NetUtils.sis",
    "nEzumi 2.sis",
    "RevoSDK.zip",
    "SCOMMSW.SIS",

    # pilowar
    "cclock.sis",
    "japoleon.sis",
    "GeneWar.sis",
    "Re-mem.app",
    "RateCalc.sis",
    "CubeLine.sis",
    "WinEPOC.sis",
    "PsiStatsPro.sis",
])

LANGUAGE_EMOJI = {
    "en_GB": "🇬🇧",
    "de_DE": "🇩🇪",
    "en_US": "🇺🇸",
    "en_AU": "🇦🇺",
    "fr_FR": "🇫🇷",
    "it_IT": "🇮🇹",
    "nl_NL": "🇳🇱",
    "es_ES": "🇪🇸",
    "cs_CZ": "🇨🇿",
    "bg_BG": "🇧🇬",
    "hu_HU": "🇭🇺",
    "pl_PL": "🇵🇱",
    "ru_RU": "🇷🇺",
    "no_NO": "🇳🇴",
    "sv_SE": "🇸🇪",
    "da_DK": "🇩🇰",
    "en_NZ": "🇳🇿",
    "de_CH": "🇨🇭",
    "fi_FI": "🇫🇮",
    "fr_BE": "🇧🇪",
    "nl_BE": "🇧🇪",
    "fr_CH": "🇨🇭",
    "pt_PT": "🇵🇹",
}

LIBRARY_INDEXES = [
    "library/epocgames",
    "library/epocgraphics",
    "library/epocmap",
    "library/epocmisc",
    "library/epocmoney",
    "library/epocprog",
    "library/epocutil",
    "library/epocvault",
    "library/geofox",
    "library/msgsuite",
    "library/pcba",
    "library/psiwin",
    "library/revogames",
    "library/s3comms",
    "library/s3games",
    "library/s3graphics",
    "library/s3mapping",
    "library/s3misc",
    "library/s3money",
    "library/s3prog",
    "library/s3units",
    "library/s3util",
    "library/s3vault",
    "library/s7games",
    "library/siena",
]

LANGUAGE_ORDER = ["en_GB", "en_US", "en_AU", "fr_FR", "de_DE", "it_IT", "nl_NL", "bg_BG", ""]


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


class LibraryMetadataProvider(object):

    def __init__(self, path):
        self.path = path
        self.descriptions = {}
        for index_path in LIBRARY_INDEXES:
            with open(os.path.join(path, index_path) + ".htm") as fh:
                for line in fh.readlines():
                    match = re.match(r"^(\S+)\s+(\d{2}/\d{2}/\d{2})\s+(.+)$", line)
                    if not match:
                        continue
                    application_path = os.path.join(path, index_path, match.group(1)).lower()
                    self.descriptions[application_path] = match.group(3)
                    if not os.path.exists(application_path):
                        logging.warning("WARN: Missing application path", application_path)

    def summary_for(self, path):
        directory = os.path.dirname(path).lower()
        while directory != "/":
            if directory in self.descriptions:
                return self.descriptions[directory]
            directory = os.path.dirname(directory)
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
        self.variants = group_collections(installers, lambda x: x.sha256)

    @property
    def version(self):
        return self.installers[0].version

    def as_dict(self, relative_icons_path):
        return {
            'version': self.version,
            'variants': [variant.as_dict(relative_icons_path=relative_icons_path) for variant in self.variants],
        }


class Program(object):

    def __init__(self, uid, installers, screenshots):
        self.uid = uid
        self.installers = installers  # TODO: Item / Program / Release?
        self.screenshots = screenshots
        versions = collections.defaultdict(list)
        for installer in installers:
            versions[installer.version].append(installer)
        # We use `natsort` to sort the versions to ensure, for example, 10.0 sorts _after_ 2.0.
        self.versions = natsort.natsorted([Version(installers=installers) for installers in versions.values()], key=lambda x: x.version)
        tags = set()
        for installer in installers:
            for tag in installer.tags:
                tags.add(tag)
        self.tags = tags
        kinds = set()
        for installer in installers:
            kinds.add(installer.kind)
        self.kinds = kinds


    @property
    def name(self):
        return self.installers[0].name

    @property
    def summary(self):
        return self.installers[0].summary

    @property
    def readme(self):
        for installer in self.installers:
            if installer.readme is not None:
                return installer.readme

    @property
    def icon(self):
        return select_icon([installer.icon for installer in self.installers
                            if installer.icon])

    def as_dict(self, relative_icons_path):
        dict = {
            'uid': self.uid,
            'name': self.name,
            'summary': self.summary,
            'versions': [version.as_dict(relative_icons_path=relative_icons_path) for version in self.versions],
            'tags': sorted(list(self.tags)),
            'kinds': sorted([kind.value for kind in self.kinds]),
        }
        summary = self.summary
        if summary:
            dict['summary'] = summary
        readme = self.readme
        if readme:
            dict['readme'] = readme
        icon = self.icon
        if icon:
            dict['icon'] = {
                'path': os.path.join(relative_icons_path, icon.filename),
                'width': icon.width,
                'height': icon.height,
            }
        return dict


class Release(object):

    # TODO: Rename UID to identifier everywhere.
    def __init__(self, reference, kind, identifier, sha256, name, version, icons, summary, readme, tags):
        self.reference = reference
        self.kind = kind
        self.uid = identifier
        self.sha256 = sha256
        self.name = name
        self.version = version
        self.icons = icons
        self.summary = summary
        self.readme = readme
        self.icon = select_icon(self.icons)
        self.tags = tags

    def as_dict(self, relative_icons_path):
        dict = {
            'reference': [item.as_dict() for item in self.reference],
            'kind': self.kind.value,
            'sha256': self.sha256,
            'uid': self.uid,
            'name': self.name,
            'version': self.version,
            'tags': sorted(list(self.tags)),
        }
        if self.icon is not None:
            dict['icon'] = {
                'path': os.path.join(relative_icons_path, self.icon.filename),
                'width': self.icon.width,
                'height': self.icon.height,
            }
        return dict

    def write_assets(self, icons_path):
        if self.icon is None:
            return
        self.icon.write(directory_path=icons_path)


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


def readme_for(path):
    readme_path = find_sibling(path, "readme.txt")
    if readme_path:
        with open(readme_path, "rb") as fh:
            return decode(fh.read())


def select_icon(icons):
    candidates = [icon for icon in icons if icon.width == icon.height and icon.width <= 48]
    icons = list(reversed(sorted(candidates, key=lambda x: (x.bpp, x.width))))
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
    logging.effort("Failed to select a name from candidates '%s'.", names)
    exit("Unable to find language")


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


def import_installer(source, reference, path):
    info = opolua.dumpsis(path)
    icons = []
    tags = []

    with tempfile.TemporaryDirectory() as temporary_directory_path:

        with Chdir(temporary_directory_path):
            opolua.dumpsis_extract(path, temporary_directory_path)

            tags = discover_tags(temporary_directory_path)

            contents = glob.glob("**/*.aif", recursive=True)
            if contents:
                aif_path = contents[0]
                icons = opolua.get_icons(aif_path)

    summary = source.summary_for(path)
    readme = readme_for(path)
    return Release(reference=reference,
                   kind=ReleaseKind.INSTALLER,
                   identifier="0x%08x" % info["uid"],
                   sha256=shasum(path),
                   name=select_name(info["name"]),
                   version=info["version"],
                   icons=icons,
                   summary=summary,
                   readme=readme,
                   tags=tags)


# TODO: Rename to just import?
def import_source(source, reference=None, path=None, indent=0):

    apps = []
    logging.info(" " * indent + f"Importing source '{source.path}'...")
    for (file_path, reference) in source.assets:
        basename = os.path.basename(file_path)
        name, ext = os.path.splitext(basename)
        ext = ext.lower()

        # TODO: See if this is now fixed with Tom's new detection stuff.
        if basename in IGNORED or "System/Install" in file_path:
            continue

        if ext == ".app":

            # TODO: Combine APP and SIS.

            tags = discover_tags(os.path.dirname(file_path))

            logging.info(" " * indent + f"Importing app '{file_path}'...")
            aif_path = find_sibling(file_path, name + ".aif")
            uid = shasum(file_path)
            icons = []
            app_name = name
            if aif_path:
                info = opolua.dumpaif(aif_path)
                uid = ("0x%08x" % info["uid3"]).lower()
                app_name = select_name(info["captions"])
                icons = opolua.get_icons(aif_path)
            else:
                try:
                    info = opolua.dumpaif(file_path)
                    icons = opolua.get_icons(file_path)
                    app_name = select_name(info["captions"])
                except opolua.InvalidAIF:
                    pass
                except BaseException as e:
                    logging.warning("Failed to parse APP as AIF with message '%s'", e)
            summary = source.summary_for(file_path)
            readme = readme_for(file_path)
            release = Release(reference=reference,
                              kind=ReleaseKind.STANDALONE,
                              identifier=uid,
                              sha256=shasum(file_path),
                              name=app_name,
                              version="Unknown",
                              icons=icons,
                              summary=summary,
                              readme=readme,
                              tags=tags)
            apps.append(release)

        elif ext == ".sis":

            logging.info(" " * indent + f"Importing installer '{file_path}'...")
            try:
                apps.append(import_installer(source=source, reference=reference, path=file_path))
            except opolua.InvalidInstaller as e:
                logging.error("Failed to import installer with message '%s", e)

    return apps


def index(library):

    summary_path = os.path.join(library.index_directory, "summary.json")
    sources_path = os.path.join(library.index_directory, "sources.json")
    programs_path = os.path.join(library.index_directory, "programs.json")
    icons_path = os.path.join(library.index_directory, "icons")

    # Import all the standalone apps and installers.
    releases = []
    for source in library.sources:
        releases += import_source(source)

    # Generate the library summary.
    unique_uids = set()
    unique_versions = set()
    unique_shas = set()
    total_count = 0
    details = collections.defaultdict(list)
    groups = collections.defaultdict(list)
    for release in releases:
        unique_uids.add(release.uid)
        unique_versions.add((release.uid, release.version))
        unique_shas.add(release.sha256)
        total_count = total_count + 1
        details[(release.uid, release.sha256, release.version)].append(release)
        groups[(release.uid)].append(release)
    summary = Summary(installer_count=total_count,
                      uid_count=len(unique_uids),
                      version_count=len(unique_versions),
                      sha_count=len(unique_shas))

    # Generate the library by grouping the programs together by identifier/uid.
    applications = []
    for identifier, installers in sorted([item for item in groups.items()],
                                         key=lambda x: x[1][0].name.lower()):
        applications.append(Program(identifier, installers, []))

    # Create the output directory.
    os.makedirs(library.index_directory, exist_ok=True)

    # Write the summary.
    logging.info("Writing summary '%s'...", summary_path)
    with open(summary_path, "w") as fh:
        json.dump(summary.as_dict(), fh)

    # Write the sources.
    logging.info("Writing sources '%s'...", sources_path)
    with open(sources_path, "w") as fh:
        json.dump([source.as_dict() for source in library.sources], fh)

    # Write the library.
    logging.info("Writing the library '%s'...", programs_path)
    with open(programs_path, "w", encoding="utf-8") as fh:
        json.dump([application.as_dict(relative_icons_path="icons") for application in applications], fh)

    # Iterate over all the individual standalone app and installer instances and write the assets to disk.
    if os.path.exists(icons_path):
        shutil.rmtree(icons_path)
    os.makedirs(icons_path)
    for release in releases:
        release.write_assets(icons_path=icons_path)


def overlay(library):
    logging.info("Applying overlay...")

    source_programs_path = os.path.join(library.index_directory, "programs.json")
    source_sources_path = os.path.join(library.index_directory, "sources.json")
    source_summary_path = os.path.join(library.index_directory, "summary.json")
    icons_path = os.path.join(library.index_directory, "icons")

    data_output_path = os.path.join(library.output_directory, "_data")
    screenshots_output_path = os.path.join(library.output_directory, "screenshots")
    icons_output_path = os.path.join(library.output_directory, "icons")
    api_v1_output_path = os.path.join(library.output_directory, "api", "v1")

    destination_programs_path = os.path.join(data_output_path, "programs.json")
    destination_sources_path = os.path.join(data_output_path, "sources.json")
    destination_summary_path = os.path.join(data_output_path, "summary.json")

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
            overlay_index_path = os.path.join(overlay_directory, "index.md")
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
        screenshots = overlay[identifier]["screenshots"] if "screenshots" in overlay[identifier] else []
        os.makedirs(os.path.join(screenshots_output_path, identifier))
        relative_paths = []
        for screenshot in screenshots:
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
    with open(destination_programs_path, "w") as fh:
        json.dump(index, fh)

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true', default=False, help="show verbose output")
    parser.add_argument("definition")
    parser.add_argument("command", choices=["sync", "index", "overlay"], nargs="+", help="command to run")
    options = parser.parse_args()

    library = common.Library(options.definition)

    for command in options.command:
        if command == "sync":
            library.sync()
        if command == "index":
            index(library)
        if command == "overlay":
            overlay(library)


if __name__ == "__main__":
    main()
