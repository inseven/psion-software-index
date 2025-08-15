#!/usr/bin/env python3

import os
import sys
import tempfile
import unittest

ROOT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIRECTORY = os.path.join(ROOT_DIRECTORY, "tools")
EXAMPLES_DIRECTORY = os.path.join(ROOT_DIRECTORY, "examples")

sys.path.append(TOOLS_DIRECTORY)

import indexer

from indexer import import_installer


class ExtractionTests(unittest.TestCase):

    def _import_installer(self, path):

        errors = []
        def error_handler(error):
            errors.append(error)

        with tempfile.TemporaryDirectory() as temporary_directory:
            installer = import_installer(source={},
                                         output_directory=temporary_directory,
                                         reference=[],
                                         path=path,
                                         error_handler=error_handler)
        release = installer.as_dict(relative_icons_path="icons")
        return (release, errors)

    def test_installer_version(self):
        release, errors = self._import_installer(os.path.join(EXAMPLES_DIRECTORY, "watchdog.SIS"))
        self.assertEqual(len(errors), 0)
        self.assertEqual(release["version"], "1.06")
        self.assertEqual(release["version_components"]["major"], 1)
        self.assertEqual(release["version_components"]["minor"], 6)

    def test_import_icons(self):
        release, errors = self._import_installer(os.path.join(EXAMPLES_DIRECTORY, "baseconv7.sis"))
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(release["icons"]), 1)
        icon = release["icons"][0]
        self.assertEqual(icon['sha256'], "bde84d6d3ed948a55dbc746a140628867e572b3ca9d2ae33c25ce98499fb2c16")
        self.assertEqual(icon['width'], 48)
        self.assertEqual(icon['height'], 48)


if __name__ == "__main__":
    unittest.main()
