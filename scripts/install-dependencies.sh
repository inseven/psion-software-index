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
SITE_DIRECTORY="$ROOT_DIRECTORY/site"
ENVIRONMENT_PATH="$SCRIPTS_DIRECTORY/environment.sh"

# Install tools.
cd "$ROOT_DIRECTORY"
mise install
cd "$ROOT_DIRECTORY/dependencies/opolua"
mise install

# Create directory for local tools.
if [ -d "$ROOT_DIRECTORY/.local" ] ; then
    rm -r "$ROOT_DIRECTORY/.local"
fi

# Source the local environment configuration; this ensures tools are installed in the .local directory we just created.
source "$ENVIRONMENT_PATH"

# Install the Python dependencies
pip3 install pipenv
PIPENV_PIPFILE="$TOOLS_DIRECTORY/Pipfile" pipenv install

# Install the Ruby dependencies
gem install bundler
cd "$SITE_DIRECTORY"
bundle install
