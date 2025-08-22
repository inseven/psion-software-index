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
import os
import shutil
import time
import urllib.parse

import requests

import matplotlib.pyplot as plt

from matplotlib.ticker import FuncFormatter, MultipleLocator


def generate_charts(path, current_summary_path):

    url = f"https://api.github.com/repos/inseven/psion-software-index/releases"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Use a GitHub token if it's present in the environment as this is likely to have fewer rate limits.
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"Bearer {os.environ["GITHUB_TOKEN"]}"

    # Fetch the required data with an exponential backoff (max 5m) if we hit a 403 rate limit.
    # TODO: Support paging.
    attempt = 1
    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            break
        elif response.status_code == 403:
            sleep_duration_s = min(300, 2 ** attempt)
            logging.info(f"Waiting {sleep_duration_s}s for GitHub API rate limits...")
            time.sleep(sleep_duration_s)
            attempt += 1
            continue
        else:
            response.raise_for_status()

    summaries = []
    releases = response.json()
    for release in releases:
        if release['prerelease']:
            continue
        release_name = release['name']
        assets = {asset['name']: asset['browser_download_url'] for asset in release.get('assets', [])}
        if 'summary.json' in assets:
            summary_response = requests.get(assets['summary.json'])
            summaries.append({'version': release_name, 'summary': summary_response.json()})
    summaries.reverse()

    with open(current_summary_path) as fh:
        summaries.append({'version': 'Current', 'summary': json.load(fh)})

    versions = [summary['version'] for summary in summaries]

    def new_plot():
        plt.figure(figsize=(6,4), constrained_layout=True)

    def configure_plot():
        plt.xlabel("Software Index Release")
        plt.xticks(rotation=90)
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.ylim(bottom=0)
        plt.legend()

    new_plot()
    plt.plot(versions, [summary['summary']['programs']['epoc16'] for summary in summaries], marker='o', label="EPOC16")
    plt.plot(versions, [summary['summary']['programs']['epoc32'] for summary in summaries], marker='o', label="EPOC32")
    plt.title("Programs")
    configure_plot()
    plt.gca().yaxis.set_major_locator(MultipleLocator(2000))
    plt.savefig(os.path.join(path, "programs.png"), dpi=300)

    new_plot()
    plt.plot(versions, [summary['summary']['releases']['unique']['epoc16'] for summary in summaries], marker='o', label="EPOC16")
    plt.plot(versions, [summary['summary']['releases']['unique']['epoc32'] for summary in summaries], marker='o', label="EPOC32")
    plt.title("Releases")
    configure_plot()
    plt.gca().yaxis.set_major_locator(MultipleLocator(2000))
    plt.savefig(os.path.join(path, "releases.png"), dpi=300)

    new_plot()
    plt.plot(versions, [summary['summary']['size']['unique']['epoc16'] / 1024 / 1024 for summary in summaries], marker='o', label="EPOC16")
    plt.plot(versions, [summary['summary']['size']['unique']['epoc32'] / 1024 / 1024 for summary in summaries], marker='o', label="EPOC32")
    plt.title("Size")
    configure_plot()
    plt.gca().yaxis.set_major_locator(MultipleLocator(512))
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.0f} MB"))
    plt.savefig(os.path.join(path, "size.png"), dpi=300)

    new_plot()
    plt.plot(versions, [summary['summary']['sources'] for summary in summaries], marker='o', label="EPOC16")
    plt.title("Sources")
    configure_plot()
    plt.savefig(os.path.join(path, "sources.png"), dpi=300)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="output directory")
    parser.add_argument("summary", help="path to the current summary")
    options = parser.parse_args()

    generate_charts(os.path.abspath(options.output), os.path.abspath(options.summary))


if __name__ == "__main__":
    main()