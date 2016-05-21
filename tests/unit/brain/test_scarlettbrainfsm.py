# This file is part of Scarlett.
# Copyright 2014, Behanceops.

import scarlett
import sys
from tests.unit import unittest, ScarlettTestCase
from nose.plugins.attrib import attr


class ScarlettBrainFsmTestCase(ScarlettTestCase):

    def setUp(self):
        super(ScarlettBrainFsmTestCase, self).setUp()

    @attr(brain=True, redis=True, threading=True)
    def test_scarlett_attributes(self):
        pass


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
