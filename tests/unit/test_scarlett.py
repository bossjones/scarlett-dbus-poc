# This file is part of Scarlett.
# Copyright 2014, Behanceops.

import scarlett
import sys
from tests.unit import unittest, ScarlettTestCase
from nose.plugins.attrib import attr


class ScarlettSystemTestCase(ScarlettTestCase):

    def setUp(self):
        super(ScarlettSystemTestCase, self).setUp()

    @attr(scarlettsystem=True, dbus=True)
    def test_scarlett_system(self):
        ss_test = scarlett.ScarlettSystem()
        self.assertTrue(
            'Scarlett 0.5.0 (linux2)' in ss_test.scarlett_version_info, True)
        self.assertTrue('Python 2.7.3' in ss_test.scarlett_version_info, True)
        self.assertTrue('PyGst 0.10' in ss_test.scarlett_version_info, True)
        self.assertTrue(
            'Gobject (2, 32, 4)' in ss_test.scarlett_version_info, True)
        self.assertTrue(
            'org.scarlettapp.scarlettdaemon' in ss_test.DBUS_NAME, True)
        self.assertTrue(
            '/org/scarlettapp/scarlettdaemon' in ss_test.DBUS_PATH, True)
        self.assertEqual(ss_test.brain, None)
        self.assertEqual(ss_test.player, None)
        self.assertEqual(ss_test.speaker, None)
        self.assertEqual(ss_test.base_services, [])
        self.assertEqual(ss_test.features, [])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
