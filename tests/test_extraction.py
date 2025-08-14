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

    def test_import_installer(self):

        errors = []
        def error_handler(error):
            errors.append(error)

        with tempfile.TemporaryDirectory() as temporary_directory:
            installer = import_installer(source={},
                                         output_directory=temporary_directory,
                                         reference=[],
                                         path=os.path.join(EXAMPLES_DIRECTORY, "watchdog.SIS"),
                                         error_handler=error_handler)
        installer_dictionary = installer.as_dict(relative_icons_path="icons")
        self.assertEqual(installer_dictionary["version"], "1.06")


if __name__ == "__main__":
    unittest.main()
