#!/bin/bash

# Copyright (c) 2026 Jason Morley
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

ROOT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
SITE_DIRECTORY="$ROOT_DIRECTORY/_site"
WORKER_DIRECTORY="$ROOT_DIRECTORY/workers/software-psion-community"

ENV_PATH="$ROOT_DIRECTORY/.env"

if [ -f "$ENV_PATH" ]; then
    source "$ENV_PATH"
fi

{ set +x; } 2>/dev/null
export RCLONE_S3_ACCESS_KEY_ID=$WEBSITE_BUCKET_ACCESS_KEY_ID
export RCLONE_S3_SECRET_ACCESS_KEY=$WEBSITE_BUCKET_SECRET_ACCESS_KEY
set -x

rclone sync \
    "$SITE_DIRECTORY" \
    ":s3,provider=Cloudflare,endpoint='$WEBSITE_BUCKET_ENDPOINT_URL',no_check_bucket=true:$WEBSITE_BUCKET_NAME" \
    --checksum \
    --fast-list \
    --exclude .DS_Store \
    --transfers 32 \
    --stats 30s \
    --stats-one-line

cd "$WORKER_DIRECTORY"
npx cf deploy
