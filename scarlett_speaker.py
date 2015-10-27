#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import threads_init
import gobject
gobject.threads_init()
threads_init()

import pygst
pygst.require('0.10')
import gst

import StringIO
import os
import sys
import re
import ConfigParser
import signal

from IPython.core.debugger import Tracer
from IPython.core import ultratb

from gettext import gettext as _

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

from colorlog import ColoredFormatter

import logging


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "(%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt=None,
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
logger = setup_logger()


class ScarlettSpeaker():

    def __init__(self, sound):
        global logger
        self._loop = gobject.MainLoop()

        # Element playbin automatic plays any sound
        espeak_pipeline = 'espeak name=source ! autoaudiosink'
        self.player = gst.parse_launch(espeak_pipeline)

        ####################################################################################
        # all writable properties(including text) make sense only at start playing;
        # to apply new values you need to stop pipe.set_state(gst.STATE_NULL) pipe and
        # start it again with new properties pipe.set_state(gst.STATE_PLAYING).
        # source: http://wiki.sugarlabs.org/go/Activity_Team/gst-plugins-espeak
        ####################################################################################
        # Set the uri to the sound
        source = self.player.get_by_name("source")
        source.props.pitch = 50
        source.props.rate = 100
        source.props.voice = "en+f3"
        source.props.text = _('{}'.format(sound))

        # Enable message bus to check for errors in the pipeline
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

    def run(self):
        self.player.set_state(gst.STATE_PLAYING)
        self._loop.run()

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self._loop.quit()
            self.quit()
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self._loop.quit()
            self.quit()

    def quit(self):
        logger.debug("  shutting down ScarlettSpeaker")
