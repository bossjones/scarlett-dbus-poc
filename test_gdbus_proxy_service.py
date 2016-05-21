#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# NOTE: This is the new task_runner
# NOTE: [02/21/2016]

import os
import sys
import time
import argparse
import pprint
pp = pprint.PrettyPrinter(indent=4)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
import threading

from pydbus import SessionBus

GObject.threads_init()
Gst.init(None)

print '********************************************************'
print 'GObject: '
pp.pprint(GObject.pygobject_version)
print ''
print 'Gst: '
pp.pprint(Gst.version_string())
print '********************************************************'

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

import StringIO
import re
import ConfigParser
import signal
from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

from colorlog import ColoredFormatter
import logging
import scarlett_config
from gettext import gettext as _

gst = Gst

SCARLETT_DEBUG = False


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "(%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        },
        secondary_log_colors={
            'message': {
                'ERROR': 'red',
                'CRITICAL': 'red',
                'DEBUG': 'yellow'
            }
        },
        style='%'
    )

    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    return logger


logger = setup_logger()

# NOTE: enumerate req to iterate through tuple and find GVariant


def player_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("player_cb PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(args)
    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug("Type v: {}".format(type(v)))
            logger.debug("Type i: {}".format(type(i)))
        if type(v) is gi.overrides.GLib.Variant:
            if SCARLETT_DEBUG:
                logger.debug("THIS SHOULD BE A Tuple now: {}".format(v))
            msg, scarlett_sound = v
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))

# NOTE: enumerate req to iterate through tuple and find GVariant


def command_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("player_cb PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(args)
    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug("Type v: {}".format(type(v)))
            logger.debug("Type i: {}".format(type(i)))
        if type(v) is gi.overrides.GLib.Variant:
            if SCARLETT_DEBUG:
                logger.debug("THIS SHOULD BE A Tuple now: {}".format(v))
            msg, scarlett_sound, command = v
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))
            logger.warning(" command: {}".format(command))

# with SessionBus() as bus:
bus = SessionBus()
# bus.watch_name("org.scarlett.Listener.SttFailedSignal", 0, player_cb)
ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')

# SttFailedSignal / player_cb
ss_failed_signal = bus.con.signal_subscribe(None,
                                            "org.scarlett.Listener",
                                            "SttFailedSignal",
                                            '/org/scarlett/Listener',
                                            None,
                                            0,
                                            player_cb)
# ss.emitConnectedToListener("ScarlettProxy")

# ListenerReadySignal / player_cb
ss_rdy_signal = bus.con.signal_subscribe(None,
                                         "org.scarlett.Listener",
                                         "ListenerReadySignal",
                                         '/org/scarlett/Listener',
                                         None,
                                         0,
                                         player_cb)


# KeywordRecognizedSignal / player_cb
ss_kw_rec_signal = bus.con.signal_subscribe(None,
                                            "org.scarlett.Listener",
                                            "KeywordRecognizedSignal",
                                            '/org/scarlett/Listener',
                                            None,
                                            0,
                                            player_cb)

# CommandRecognizedSignal /command_cb
ss_cmd_rec_signal = bus.con.signal_subscribe(None,
                                             "org.scarlett.Listener",
                                             "CommandRecognizedSignal",
                                             '/org/scarlett/Listener',
                                             None,
                                             0,
                                             command_cb)

# ListenerCancelSignal / player_cb
ss_cancel_signal = bus.con.signal_subscribe(None,
                                            "org.scarlett.Listener",
                                            "ListenerCancelSignal",
                                            '/org/scarlett/Listener',
                                            None,
                                            0,
                                            player_cb)


logger.debug("ss PrettyPrinter: ")
pp = pprint.PrettyPrinter(indent=4)
pp.pprint(ss)


def sigint_handler(*args):
    """Exit on Ctrl+C"""

    # Unregister handler, next Ctrl-C will kill app
    # TOD: figure out if this is really needed or not
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    GLib.MainLoop().quit()

signal.signal(signal.SIGINT, sigint_handler)

try:

    GLib.MainLoop().run()

finally:

    print 'Proxy text finished'
