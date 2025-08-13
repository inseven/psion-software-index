# Copyright (c) 2024-2025 Jason Morley
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

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from io import BytesIO

from PIL import Image as PILImage, ImageOps


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)
OPOLUA_DIRECTORY = os.path.join(ROOT_DIRECTORY, "dependencies", "opolua")
DUMPAIF_PATH = os.path.join(OPOLUA_DIRECTORY, "src", "dumpaif.lua")
DUMPSIS_PATH = os.path.join(OPOLUA_DIRECTORY, "src", "dumpsis.lua")
RECOGNIZE_PATH = os.path.join(OPOLUA_DIRECTORY, "src", "recognize.lua")

UNSUPPORTED_MESSAGE = "Only ER5 SIS files are supported"
NOT_AN_AI_MESSAGE = "Not an AIF file"

try:
    LUA_PATH = os.environ["LUA_PATH"]
except KeyError:
    # By default we respect the default version of lua specified in .tool-versions.
    LUA_PATH = subprocess.check_output(["mise", "which", "lua", "--cd", OPOLUA_DIRECTORY]).decode("utf-8").strip()


class InvalidInstaller(Exception):
    pass


class InvalidAIF(Exception):
    pass


class Image(object):

    def __init__(self, width, height, bpp, source):
        self.width = width
        self.height = height
        self.bpp = bpp
        self._source = source
        self._shasum = None

    @property
    def data(self):
        with BytesIO() as output:
            self._source.save(output, format="GIF")
            return output.getvalue()

    @property
    def shasum(self):
        if self._shasum is None:
            sha256 = hashlib.sha256()
            sha256.update(self.data)
            self._shasum = sha256.hexdigest()
        return self._shasum

    @property
    def filename(self):
        return self.shasum + ".gif"

    def write(self, directory_path):
        self._source.save(os.path.join(directory_path, self.filename), format="GIF")


def run_json_command(command, path):
    result = subprocess.run([LUA_PATH, command, "--json", path], capture_output=True)
    stdout = result.stdout.decode('utf-8')
    stderr = result.stderr.decode('utf-8')

    if UNSUPPORTED_MESSAGE in stdout + stderr:
        raise InvalidInstaller(stdout + stderr)
    elif NOT_AN_AI_MESSAGE in stdout + stderr:
        raise InvalidAIF(stdout + stderr)

    # Check the return code.
    # It might be nicer to mark
    try:
        result.check_returncode()
    except:
        print("stderr")
        print(stderr)
        print("stdout")
        print(stdout)
        raise

    return json.loads(stdout)


def dumpsis(path):
    return run_json_command(DUMPSIS_PATH, path)


def dumpaif(path):
    return run_json_command(DUMPAIF_PATH, path)


def dumpsis_extract(source, destination):
    result = subprocess.run([LUA_PATH, DUMPSIS_PATH, source, destination], capture_output=True)

    # Sadly we ignore foreign characters right now and using CP1252 by default.
    stdout = result.stdout.decode('utf-8')
    stderr = result.stderr.decode('utf-8')

    if "Illegal byte sequence" in stdout + stderr:
        return None

    # Check the return code.
    try:
        result.check_returncode()
    except:
        print("stderr")
        print(stderr)
        print("stdout")
        print(stdout)
        raise


def get_icons(aif_path):
    aif_path = os.path.abspath(aif_path)
    with tempfile.TemporaryDirectory() as directory_path:
        aif_basename = os.path.basename(aif_path)
        temporary_aif_path = os.path.join(directory_path, aif_basename)
        shutil.copyfile(aif_path, temporary_aif_path)
        subprocess.check_output([LUA_PATH, DUMPAIF_PATH, "-e", temporary_aif_path])
        aif_basename = os.path.basename(temporary_aif_path)
        aif_dirname = os.path.dirname(temporary_aif_path)
        icon_candidates = os.listdir(aif_dirname)
        icons = []
        for candidate in icon_candidates:
            match = re.match("^" + aif_basename + r"_(\d)_(\d+)x(\d+)_(\d)bpp.bmp$", candidate)
            if match:
                index = match.group(1)
                width = int(match.group(2))
                height = int(match.group(3))
                bpp = int(match.group(4))
                asset_path = os.path.join(aif_dirname, candidate)

                # Load the mask if it exists.
                mask = None
                mask_path = os.path.join(aif_dirname, f"{aif_basename}_{index}_mask_{width}x{height}_2bpp.bmp")
                if os.path.exists(mask_path):
                    with PILImage.open(mask_path) as m:
                        mask = m.convert("L").point(lambda i: i * 85)
                        mask = ImageOps.invert(mask)

                # Load the image.
                with PILImage.open(asset_path) as image, BytesIO() as output:
                    image_copy = image.convert("RGBA")
                    if mask:
                        image_copy.putalpha(mask)
                    icons.append(Image(width, height, bpp, image_copy))
        return icons


def recognize(path):
    logging.debug("Recognizing '%s'...", path)
    try:
        return run_json_command(RECOGNIZE_PATH, path)
    except:
        return {"type": "unknown"}
