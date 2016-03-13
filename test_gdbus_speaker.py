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
from gi.repository import GObject
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
import threading

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

SCARLETT_CANCEL = "pi-cancel"
SCARLETT_LISTENING = "pi-listening"
SCARLETT_RESPONSE = "pi-response"
SCARLETT_FAILED = "pi-response2"

from gettext import gettext as _

gst = Gst

import scarlett_gstutils
import scarlett_config
from scarlett_log import log
from functools import wraps


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


# Create a player
PWD = '/home/pi/dev/bossjones-github/scarlett-dbus-poc'
logger = setup_logger()

gst = Gst
from functools import wraps

# source: https://github.com/jcollado/pygtk-webui/blob/master/demo.py


def trace(func):
    """Tracing wrapper to log when function enter/exit happens.
    :param func: Function to wrap
    :type func: callable
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug('Start {!r}'. format(func.__name__))
        result = func(*args, **kwargs)
        logger.debug('End {!r}'. format(func.__name__))
        return result
    return wrapper


# def sigint_handler(*args):
#     """Exit on Ctrl+C"""
#
#     # Unregister handler, next Ctrl-C will kill app
#     # TODO: figure out if this is really needed or not
#     signal.signal(signal.SIGINT, signal.SIG_DFL)
#
# signal.signal(signal.SIGINT, sigint_handler)


class ScarlettSpeaker():

    @trace
    def __init__(self, cmd):
        global PWD
        global logger
        self.loop = GLib.MainLoop()
        self.pipelines_stack = []
        self.source_stack = []

        self._message = 'This is the ScarlettSpeaker'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = False

        #######################################################################
        espeak_pipeline = 'espeak name=source ! queue2 name=q ! autoaudiosink'
        player = Gst.parse_launch(espeak_pipeline)
        print '********************************************************'
        print 'player from espeak_pipeline: '
        pp.pprint(player)
        print '********************************************************'
        self.end_cond = threading.Condition(threading.Lock())

        #######################################################################
        # all writable properties(including text) make sense only at start playing;
        # to apply new values you need to stop pipe.set_state(Gst.State.NULL) pipe and
        # start it again with new properties pipe.set_state(Gst.State.PLAYING).
        # source: http://wiki.sugarlabs.org/go/Activity_Team/gst-plugins-espeak
        #######################################################################
        # Set the uri to the cmd
        source = player.get_by_name("source")
        source.props.pitch = 50
        source.props.rate = 20
        source.props.voice = "en+f3"
        source.props.text = _('{}'.format(cmd))
        self.text = source.props.text

        # Enable message bus to check for errors in the pipeline
        gst_bus = player.get_bus()
        gst_bus.add_signal_watch()

        # NOTE: Borrowed these lines from gnome-music
        gst_bus.connect('message::error', self._onBusError)
        # gst_bus.connect('message::eos', self._on_bus_eos)
        # gst_bus.connect("message", self._on_message_cb)

        self.pipelines_stack.append(player)
        self.source_stack.append(source)

        # pp.pprint(dir(source))

        logger.debug("ScarlettSpeaker __init__ finished")

        self.mainloopthread = scarlett_gstutils.MainloopThread(self.loop)
        self.mainloopthread.start()

        # start pipeline
        player.set_state(Gst.State.PLAYING)

        GST_CLOCK_TIME_NONE = 18446744073709551615

        # wait for preroll or error
        msg = gst_bus.timed_pop_filtered(
            GST_CLOCK_TIME_NONE, Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR)

        if msg.type == Gst.MessageType.ASYNC_DONE:
            ret, dur = player.query_duration(Gst.Format.TIME)
            print "Duration: %u seconds" % (dur / Gst.SECOND)

        # wait for EOS or error
        msg = gst_bus.timed_pop_filtered(
            GST_CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR)

        if msg.type == Gst.MessageType.ERROR:
            gerror, dbg_msg = msg.parse_error()
            print "Error         : ", gerror.message
            print "Debug details : ", dbg_msg

        if msg.type == Gst.MessageType.EOS:
            player.send_event(Gst.Event.new_eos())
            self.loop.quit()
            self.quit()

        print "ScarlettSpeaker stopped"
        player.set_state(Gst.State.NULL)

        # while True:
        #     try:
        #         msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
        #         if msg:
        #             if msg.type == Gst.MessageType.EOS:
        #                 logger.debug("OKAY, Gst.MessageType.EOS: ".format(Gst.MessageType.EOS))
        #                 time.sleep(10)
        #                 # player.set_state(Gst.State.NULL)
        #                 # self.loop.quit()
        #                 # self.quit()
        #                 break
        #             if msg.type == Gst.MessageType.ERROR:
        #                 logger.debug("OKAY, Gst.MessageType.ERROR: ".format(Gst.MessageType.ERROR))
        #                 time.sleep(10)
        #                 # player.set_state(Gst.State.NULL)
        #                 # self.loop.quit()
        #                 # self.end_reached = True
        #                 # try:
        #                 #     err, debug = msg.parse_error()
        #                 #     self.error_msg = "Error: %s" % err, debug
        #                 # except:
        #                 #     print 'Could not catch error message'
        #                 # # self.end_cond.notify()
        #                 # # self.end_cond.release()
        #                 # self.quit()
        #                 break
        #     except KeyboardInterrupt:
        #         player.send_event(Gst.Event.new_eos())

        # Free resources
        # player.set_state(Gst.State.NULL)

    # def release(self):
    #     if hasattr(self, 'eod') and hasattr(self, 'loop'):
    #         self.end_cond.acquire()
    #         while not hasattr(self, 'end_reached'):
    #             self.end_cond.wait()
    #         self.end_cond.release()
    #     if hasattr(self, 'error_msg'):
    #         raise IOError(self.error_msg)

    @trace
    def run(self):
        logger.debug("ScarlettSpeaker sound: {}".format(self.sound))
        self.loop.run()

    @trace
    def _on_bus_state_changed(self, bus, message):
        # Note: not all state changes are signaled through here, in particular
        # transitions between Gst.State.READY and Gst.State.NULL are never async
        # and thus don't cause a message
        # In practice, self means only Gst.State.PLAYING and Gst.State.PAUSED
        # are
        pass

    @trace
    def _onBusError(self, bus, message):
        logger.debug("_onBusError")
        p = self.pipelines_stack[0]
        p.set_state(Gst.State.NULL)
        try:
            self.loop.quit()
        except:
            print 'ERROR TRYING TO EXIT OUT FOOL'
        return True

    @trace
    def _on_bus_eos(self, bus, message):
        logger.debug("_on_bus_eos")
        p = self.pipelines_stack[0]
        p.set_state(Gst.State.NULL)
        try:
            self.loop.quit()
            # self.quit()
        except:
            print 'ERROR TRYING TO EXIT OUT FOOL'
        return True

    @trace
    def quit(self):
        return
        # logger.debug("  shutting down ScarlettSpeaker")
        # time.sleep(2)
        # self.quit()
        # return

#
# def sigint_handler(*args):
#     """Exit on Ctrl+C"""
#
#     # Unregister handler, next Ctrl-C will kill app
#     # TODO: figure out if this is really needed or not
#     signal.signal(signal.SIGINT, signal.SIG_DFL)
#
# signal.signal(signal.SIGINT, sigint_handler)
