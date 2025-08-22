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

ROOT_DIRECTORY="${SCRIPTS_DIRECTORY}/.."
BUILD_DIRECTORY="${ROOT_DIRECTORY}/build"
TEMPORARY_DIRECTORY="${ROOT_DIRECTORY}/temp"
ARCHIVES_DIRECTORY="${ROOT_DIRECTORY}/archives"
SPARKLE_DIRECTORY="${SCRIPTS_DIRECTORY}/Sparkle"

KEYCHAIN_PATH="${TEMPORARY_DIRECTORY}/temporary.keychain"
ARCHIVE_PATH="${BUILD_DIRECTORY}/Reconnect.xcarchive"
ENV_PATH="${ROOT_DIRECTORY}/.env"

RELEASE_SCRIPT_PATH="${SCRIPTS_DIRECTORY}/release.sh"

RELEASE_NOTES_TEMPLATE_PATH="${SCRIPTS_DIRECTORY}/release-notes.html"

IOS_XCODE_PATH=${IOS_XCODE_PATH:-/Applications/Xcode.app}
MACOS_XCODE_PATH=${MACOS_XCODE_PATH:-/Applications/Xcode.app}

source "${SCRIPTS_DIRECTORY}/environment.sh"

# Check that the GitHub command is available on the path.
which gh || (echo "GitHub cli (gh) not available on the path." && exit 1)

# Process the command line arguments.
POSITIONAL=()
RELEASE=${RELEASE:-false}
while [[ $# -gt 0 ]]
do
    key="$1"
    case $key in
        -r|--release)
        RELEASE=true
        shift
        ;;
        *)
        POSITIONAL+=("$1")
        shift
        ;;
    esac
done

cd "$ROOT_DIRECTORY"

# Determine the version and build number.
VERSION_NUMBER=`changes version`
BUILD_NUMBER=`build-tools generate-build-number`

echo $VERSION_NUMBER
echo $BUILD_NUMBER

if $RELEASE ; then

    changes \
        release \
        --skip-if-empty \
        --push \
        --exec "${RELEASE_SCRIPT_PATH}" \
        "${RELEASE_ZIP_PATH}" "${ZIP_PATH}" "$BUILD_DIRECTORY/appcast.xml"

fi
