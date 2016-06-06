#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import time

SCARLETT_DEBUG = None

if SCARLETT_DEBUG:
    # Setting GST_DEBUG_DUMP_DOT_DIR environment variable enables us to have a
    # dotfile generated
    os.environ[
        "GST_DEBUG_DUMP_DOT_DIR"] = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug"
    os.putenv('GST_DEBUG_DUMP_DIR_DIR',
              '/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug')


import argparse
import pprint
pp = pprint.PrettyPrinter(indent=4)

import gi
gi.require_version('Gst', '1.0')
# from gi.repository import GObject
# from gi.repository import GLib
# import threading

# from gettext import gettext as _
from pydbus import SessionBus

valid_signals = ['failed',
                 'ready',
                 'kw-rec',
                 'cmd-rec',
                 'cancel',
                 'cmd-rec']

from IPython.core.debugger import Tracer  # NOQA
from IPython.core import ultratb
import generator_utils

import logging
logger = logging.getLogger('scarlettlogger')

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)


def main(ss, args):
    if args.signal == 'failed':
        ss.emitSttFailedSignal()

    if args.signal == 'ready':
        ss.emitListenerReadySignal()

    if args.signal == 'kw-rec':
        ss.emitKeywordRecognizedSignal()

    if args.signal == 'cmd-rec':
        ss.emitCommandRecognizedSignal('what time is it')

    if args.signal == 'cancel':
        ss.emitListenerCancelSignal()

if __name__ == '__main__':
    from pydbus import SessionBus
    bus = SessionBus()
    ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')
    time.sleep(0.5)

    parser = argparse.ArgumentParser(description='Test emit signal.')
    parser.add_argument('-s',
                        '--signal',
                        help='signal to carry out.  Can be one of:\n'
                             'failed\n'
                             'ready\n'
                             'kw-rec\n'
                             'cancel\n'
                             'cmd-rec',
                        choices=valid_signals)

    args = parser.parse_args()

    main(ss, args)
