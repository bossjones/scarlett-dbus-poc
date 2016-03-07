# This file is part of Scarlett.
# Copyright 2014, Behanceops.

import sys
import time
import datetime
from tests.unit import unittest
from nose.plugins.attrib import attr


class GstImprovedTest(unittest.TestCase):

    def setUp(self):
        super(GstImprovedTest, self).setUp()

    @attr('notdefault', 'gst_improved')
    def test_gi(self):
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        self.assertTrue(Gst.version_string(), 'GStreamer 1.2.1')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
