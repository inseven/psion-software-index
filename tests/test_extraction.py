#!/usr/bin/env python3

import contextlib
import os
import sys
import tempfile
import unittest

ROOT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIRECTORY = os.path.join(ROOT_DIRECTORY, "tools")
EXAMPLES_DIRECTORY = os.path.join(ROOT_DIRECTORY, "examples")

sys.path.append(TOOLS_DIRECTORY)

import indexer
import containers

from indexer import import_application, import_installer


@contextlib.contextmanager
def example_zip(path):
    with tempfile.TemporaryDirectory() as temporary_directory:
        containers.extract_zip(os.path.join(EXAMPLES_DIRECTORY, path), temporary_directory)
        yield temporary_directory


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

    def _import_application(self, path):

        errors = []
        def error_handler(error):
            errors.append(error)

        with tempfile.TemporaryDirectory() as temporary_directory:
            installer = import_application(source={},
                                           output_directory=temporary_directory,
                                           reference=[],
                                           path=path,
                                           error_handler=error_handler)
        release = installer.as_dict(relative_icons_path="icons")
        return (release, errors)

    def test_installer_version(self):
        release, errors = self._import_installer(os.path.join(EXAMPLES_DIRECTORY, "watchdog.SIS"))
        self.assertEqual(len(errors), 0)
        print(release)
        self.assertEqual(release["version"]["major"], 1)
        self.assertEqual(release["version"]["minor"], 6)

    def test_application_version(self):
        with example_zip("blackjack5.zip") as path:
            app_path = os.path.join(path, "blackjack5.app")
            self.assertTrue(os.path.exists(app_path))
            release, errors = self._import_application(app_path)

            self.assertTrue("version" not in release)

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
