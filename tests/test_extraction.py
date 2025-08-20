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

    def test_alternative_aif_extensions(self):
        release, errors = self._import_installer(os.path.join(EXAMPLES_DIRECTORY, "Checkers.sis"))
        self.assertTrue("icons" in release)
        self.assertEqual(len(release["icons"]), 3)
        self.assertEqual(
            sorted(release["icons"], key=lambda x: x["width"]),
            [
                {
                    'filename': '9c6f11ae84be2f3c817af42e63949b798461a24ac3279a62c858317f4a84ba60.gif',
                    'width': 24,
                    'height': 24,
                    'bpp': 8,
                    'sha256': '9c6f11ae84be2f3c817af42e63949b798461a24ac3279a62c858317f4a84ba60'
                },
                {
                    'filename': 'c84338a8d2f30e74b56326378398a7c4d4a0b9ea3c8b62487115d7cb628773a8.gif',
                    'width': 32,
                    'height': 32,
                    'bpp': 8,
                    'sha256': 'c84338a8d2f30e74b56326378398a7c4d4a0b9ea3c8b62487115d7cb628773a8'
                },
                {
                    'filename': 'ae57708e5b28f22e672c4067f309ce3e274fbf3ff60cd1cf9b58fece2778f000.gif',
                    'width': 48,
                    'height': 48,
                    'bpp': 8,
                    'sha256': 'ae57708e5b28f22e672c4067f309ce3e274fbf3ff60cd1cf9b58fece2778f000'
                }
            ])

    def test_opa_resources(self):
        release, errors = self._import_application(os.path.join(EXAMPLES_DIRECTORY, "EMAILIT.OPA"))
        self.assertEqual(len(errors), 0)
        self.assertIsNotNone(release)
        self.assertEqual(
            release,
            {
                'filename': 'EMAILIT.OPA',
                'size': 45069,
                'reference': [],
                'kind': 'standalone',
                'sha256': '21ce4b6bf58db9b616f02792d18cc0fff854bca02fec0cc69faf7f9234ad03eb',
                'uid': '21ce4b6bf58db9b616f02792d18cc0fff854bca02fec0cc69faf7f9234ad03eb',
                'name':
                'eMailIt',
                'tags': ['opl', 'sibo', 'sis'],
                'icons': [
                    {
                        'filename': 'd6536c02d9edaa8d23eb0d7da9d35c609bf8d1abd0802e0b6425cee7ef9ce56c.gif',
                        'width': 48,
                        'height': 48,
                        'bpp': 1,
                        'sha256': 'd6536c02d9edaa8d23eb0d7da9d35c609bf8d1abd0802e0b6425cee7ef9ce56c'
                    },
                    {
                        'filename': '7dc76ade97a747bb5520f7b18610920fcf1ad309a63d97bc63aa4dcfd1ee5871.gif',
                        'width': 48,
                        'height': 48,
                        'bpp': 1,
                        'sha256': '7dc76ade97a747bb5520f7b18610920fcf1ad309a63d97bc63aa4dcfd1ee5871'
                    }
                ]
            })


if __name__ == "__main__":
    unittest.main()
