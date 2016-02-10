#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#### DISABLED BOSSJONES # import pprint
#### DISABLED BOSSJONES # import dbus
#### DISABLED BOSSJONES # import dbus.service
#### DISABLED BOSSJONES # import dbus.mainloop.glib
#### DISABLED BOSSJONES # from dbus.mainloop.glib import threads_init
#### DISABLED BOSSJONES # import gobject
#### DISABLED BOSSJONES # gobject.threads_init()
#### DISABLED BOSSJONES # threads_init()
#### DISABLED BOSSJONES #
#### DISABLED BOSSJONES # import pygst
#### DISABLED BOSSJONES # pygst.require('0.10')
#### DISABLED BOSSJONES # import gst

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from dbus.mainloop.glib import threads_init


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

GObject.threads_init()
Gst.init(None)
threads_init()
DBusGMainLoop(set_as_default=True)

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
import os
import sys
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
import time
import scarlett_gstutils


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "%(asctime)s.%(msecs)03d (%(threadName)-9s) %(filename)s %(funcName)s %(module)s %(processName)s %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt='%Y-%m-%d,%H:%M:%S',
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red',
        },
        secondary_log_colors={
            'message': {
                'ERROR':    'red',
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

# Create a player
PWD = '/home/pi/dev/bossjones-github/scarlett-dbus-poc'
logger = setup_logger()

gst = Gst


class ScarlettPlayer():

    def __init__(self, sound):
        global PWD
        global logger
        self._loop = GLib.MainLoop()
        self.debug = False

        # Element playbin automatic plays any sound
        self.player = gst.element_factory_make("playbin2", "player")
        self.end_cond = threading.Condition(threading.Lock())

        # Set the uri to the sound
        filename = '%s/static/sounds/%s.wav' % (PWD, sound)
        self.player.set_property('uri', 'file://%s' % filename)
        self.sound = sound

        # Enable message bus to check for errors in the pipeline
        bus = self.player.get_bus()
        bus.add_signal_watch()
        # bus.enable_sync_message_emission()
        bus.connect("message", self._on_message_cb)
        # bus.connect("message::eos", self.on_finish)
        # bus.connect('message::error', self.on_error)
        logger.debug("ScarlettPlayer __init__ finished")

        self.mainloopthread = scarlett_gstutils.MainloopThread(self._loop)
        self.mainloopthread.start()

        # start pipeline
        self.player.set_state(gst.STATE_PLAYING)

    def release(self):
        if hasattr(self, 'eod') and hasattr(self, '_loop'):
            self.end_cond.acquire()
            while not hasattr(self, 'end_reached'):
                self.end_cond.wait()
            self.end_cond.release()
        if hasattr(self, 'error_msg'):
            raise IOError(self.error_msg)

    def run(self):
        logger.debug("ScarlettPlayer sound: {}".format(self.sound))
        # self.player.set_state(gst.STATE_PLAYING)
        self._loop.run()

    def on_message(self, bus, message):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(bus)
        pp.pprint(message)
        t = message.type
        if t == gst.MESSAGE_EOS:
            logger.debug("OKAY, MESSAGE_EOS: ".format(gst.MESSAGE_EOS))
            self.player.set_state(gst.STATE_NULL)
            self._loop.quit()
            self.quit()
        elif t == gst.MESSAGE_ERROR:
            logger.debug("OKAY, MESSAGE_ERROR: ".format(gst.MESSAGE_ERROR))
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self._loop.quit()
            self.quit()

    def finish_request(self):
        self.player.set_state(gst.STATE_NULL)
        self._loop.quit()
        self.quit()
        time.sleep(2)
        return

    def _on_message_cb(self, bus, message):
        if self.debug:
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(bus)
            pp.pprint(message)
        t = message.type
        if t == gst.MESSAGE_EOS:
            logger.debug("OKAY, MESSAGE_EOS: ".format(gst.MESSAGE_EOS))
            self.end_cond.acquire()
            self.player.set_state(gst.STATE_NULL)
            self._loop.quit()
            self.end_reached = True
            self.end_cond.notify()
            self.end_cond.release()
            self.quit()

        elif t == gst.MESSAGE_ERROR:
            logger.debug("OKAY, MESSAGE_ERROR: ".format(gst.MESSAGE_ERROR))
            self.end_cond.acquire()
            self.player.set_state(gst.STATE_NULL)
            self._loop.quit()
            self.end_reached = True
            err, debug = message.parse_error()
            self.error_msg = "Error: %s" % err, debug
            self.end_cond.notify()
            self.end_cond.release()
            self.quit()

    def on_finish(self, bus, message):
        logger.debug("OKAY, on_finish. Setting state to STATE_NULL")
        self.finish_request()

    def on_error(self, bus, message):
        logger.debug("OKAY, on_error. Setting state to STATE_NULL")
        self.finish_request()

    def quit(self):
        logger.debug("  shutting down ScarlettPlayer")
