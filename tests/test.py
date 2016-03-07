#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test
----------------------------------

Tests for `scarlett` module.
"""
# insert path so we can access things w/o having to re-install everything
#sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from __future__ import print_function

import logging
import argparse
import os
import sys
#import unittest

from nose.core import run

import scarlett
#from scarlett import scarlett
#from IPython.core.debugger import Tracer


def main():
    description = ("Runs scarlett unit and/or integration tests. "
                   "Arguments will be passed on to nosetests. "
                   "See nosetests --help for more information.")
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-t', '--service-tests', action="append", default=[],
                        help="Run tests for a given service.  This will "
                        "run any test tagged with the specified value, "
                        "e.g -t listeners -t client")
    known_args, remaining_args = parser.parse_known_args()
    attribute_args = []
    for service_attribute in known_args.service_tests:
        attribute_args.extend(['-a',
                               '!notdefault,' + service_attribute,
                               '--with-coverage'
                               '-v',
                               '--cover-erase',
                               '--cover-package=scarlett'
                               '-d'])
    if not attribute_args:
        # If the user did not specify any filtering criteria, we at least
        # will filter out any test tagged 'notdefault'.
        attribute_args = [
            '-a',
            '!notdefault',
            '--with-coverage',
            '-v',
            '--cover-erase',
            '--cover-package=scarlett',
            '-d']

    # Set default tests used by e.g. tox. For Py2 this means all unit
    # tests, while for Py3 it's just whitelisted ones.
    if 'default' in remaining_args:
        # Run from the base project directory
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        for i, arg in enumerate(remaining_args):
            if arg == 'default':
                remaining_args[i] = 'tests/unit'

    if 'gst_improved' in remaining_args:
        # Run from the base project directory
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        for i, arg in enumerate(remaining_args):
            if arg == 'gst_improved':
                remaining_args[i] = 'tests/unit/future'

    all_args = [__file__] + attribute_args + remaining_args
    print("nose command:", ' '.join(all_args))
    if run(argv=all_args):
        # run will return True is all the tests pass.  We want
        # this to equal a 0 rc
        del os.environ['MAIN_DIR']
        del os.environ['SCARLETT_CONFIG']
        del os.environ['SCARLETT_HMM']
        del os.environ['SCARLETT_LM']
        del os.environ['SCARLETT_DICT']
        return 0
    else:
        return 1

if __name__ == '__main__':
    os.environ['MAIN_DIR'] = os.path.abspath(os.path.dirname(__file__))
    os.environ[
        'SCARLETT_CONFIG'] = "%s/tests/fixtures/.scarlett" % (os.environ['MAIN_DIR'])
    os.environ[
        'SCARLETT_HMM'] = "$%s/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k" % (os.environ['MAIN_DIR'])
    os.environ[
        'SCARLETT_LM'] = "$%s/tests/fixtures/lm/6253.lm" % (os.environ['MAIN_DIR'])
    os.environ[
        'SCARLETT_DICT'] = "$%s/tests/fixtures/dict/6253.dic" % (os.environ['MAIN_DIR'])
    sys.exit(main())
