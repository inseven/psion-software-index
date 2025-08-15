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
set -u

ROOT_DIRECTORY="$( cd "$( dirname "$( dirname "${BASH_SOURCE[0]}" )" )" &> /dev/null && pwd )"

SCRIPTS_DIRECTORY="$ROOT_DIRECTORY/scripts"
TOOLS_DIRECTORY="$ROOT_DIRECTORY/tools"
TESTS_DIRECTORY="$ROOT_DIRECTORY/tests"

API_V1_DIRECTORY="$ROOT_DIRECTORY/site/api/v1"

source "$SCRIPTS_DIRECTORY/environment.sh"

export PIPENV_PIPFILE="$TOOLS_DIRECTORY/Pipfile"

function validate() {
    SCHEMA="$1"
    echo "Validating '$SCHEMA'..."
    pipenv run check-jsonschema \
        --schemafile "$API_V1_DIRECTORY/$SCHEMA.schema.json" \
        "$API_V1_DIRECTORY/$SCHEMA/index.json"
}

validate "groups"
validate "programs"
validate "sources"
validate "summary"
