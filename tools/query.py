#!/usr/bin/env python3

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

import argparse
import json
import logging
import os
import sys


TOOLS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
ROOT_DIRECTORY = os.path.dirname(TOOLS_DIRECTORY)

LIBRARY_PATH = os.path.join(ROOT_DIRECTORY, "_index/library.json")

verbose = '--verbose' in sys.argv[1:] or '-v' in sys.argv[1:]
logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="[%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true', default=False, help="show verbose output")
    parser.add_argument('--tag', '-t', action="append", default=[])
    parser.add_argument('--kind', '-k', action="append", default=[])
    options = parser.parse_args()

    with open(LIBRARY_PATH) as fh:
        library = json.load(fh)

    tags = set(options.tag)
    kinds = set(options.kind)

    for program in library:
        program_tags = set(program["tags"])
        program_kinds = set(program["kinds"])
        if not program_tags.issuperset(tags):
            continue
        if not program_kinds.issuperset(kinds):
            continue
        print(program["name"])
        print(f"    https://software.psion.info/programs/{program['uid']}")


if __name__ == "__main__":
    main()
