#!/bin/bash

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

set -e
set -o pipefail
set -x
set -u

SCRIPTS_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

ROOT_DIRECTORY="$SCRIPTS_DIRECTORY/.."
TOOLS_DIRECTORY="$ROOT_DIRECTORY/tools"
INDEX_DIRECTORY="$ROOT_DIRECTORY/_index"
SITE_DIRECTORY="$ROOT_DIRECTORY/site"
SITE_DATA_DIRECTORY="$SITE_DIRECTORY/_data"


source "$SCRIPTS_DIRECTORY/environment.sh"

# Build the API documentation.
"$SCRIPTS_DIRECTORY/build-api-docs.sh"

# Generate the charts.
mkdir -p "$SITE_DIRECTORY/images/charts"
"$TOOLS_DIRECTORY/charts" "$SITE_DIRECTORY/images/charts" "$SITE_DATA_DIRECTORY/summary.json"

# Build the site.
cd "$SITE_DIRECTORY"
bundle exec jekyll build
