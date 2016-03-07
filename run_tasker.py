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
from signal import signal, SIGWINCH, SIGKILL, SIGTERM

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
import traceback
from functools import wraps
import Queue
from random import randint
from pydbus import SessionBus

# scarlett object dependencies for playing sounds and speaking
import test_gdbus_speaker
import test_gdbus_player


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

# Managing the Gobject main loop thread.

_shared_loop_thread = None
_loop_thread_lock = threading.RLock()


# NOTE: on plane to DC
def get_loop_thread():
    """Get the shared main-loop thread.
    """
    global _shared_loop_thread
    with _loop_thread_lock:
        if not _shared_loop_thread:
            # Start a new thread.
            _shared_loop_thread = ExcThread()
            _shared_loop_thread.start()
        return _shared_loop_thread


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

NUM_THREADS = 10


class ExcThread(threading.Thread):
    """
    Exception Thread Class aka Producer. Acts as the Child thread.
    Any errors that happen here will get placed into a Queue and raised for the parent thread to consume.

    A thread class that supports raising exception in the thread from another thread.
    """

    @trace
    def __init__(self, bucket, loop, *args, **kargs):
        threading.Thread.__init__(self, *args, **kargs)
        self.bucket = bucket
        self.running = True
        self._stop = threading.Event()
        # self.loop = GObject.MainLoop()
        if loop is None:
            self.loop = GObject.MainLoop()
        else:
            self.loop = loop
        # self.daemon = True

    @trace
    def run(self):
        try:
            print "Child Thread Started", self
            # # NOTE: first iteration # threading.Thread.run(self)
            # # NOTE: second iteration # self.loop.run()
            self.loop.run()
            # raise Exception('An error occured here.')
        except Exception:
            self.bucket.put(sys.exc_info())
            raise

    @trace
    def stop(self):
        self._stop.set()

    @trace
    def stopped(self):
        return self._stop.isSet()


class ScarlettTasker(threading.Thread):

    @trace
    def __init__(self, bucket, loop, *args, **kargs):
        threading.Thread.__init__(self, *args, **kargs)
        self.bucket = bucket
        self.loop = loop
        self.running = True
        self._stop = threading.Event()
        self.queue = Queue.Queue(10)

        # @trace
        # def wait_for_t(t):
        #     if not t.is_alive():
        #         # This won't block, since the thread isn't alive anymore
        #         t.join()
        #         print 'waiting.....'
        #         # Do whatever else you would do when join()
        #         # (or maybe collega_GUI?) returns
        #     else:
        #         GLib.timeout_add(200, wait_for_t, t)

        # NOTE: enumerate req to iterate through tuple and find GVariant
        @trace
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
                        logger.debug(
                            "THIS SHOULD BE A Tuple now: {}".format(v))
                    msg, scarlett_sound = v
                    logger.warning(" msg: {}".format(msg))
                    logger.warning(
                        " scarlett_sound: {}".format(scarlett_sound))
                    # NOTE: Create something like test_gdbus_player.ScarlettPlayer('pi-listening')
                    # NOTE: test_gdbus_player.ScarlettPlayer
                    # NOTE: self.bucket.put()
                    # NOTE: ADD self.queue.put(v)

        # NOTE: enumerate req to iterate through tuple and find GVariant
        @trace
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
                        logger.debug(
                            "THIS SHOULD BE A Tuple now: {}".format(v))
                    msg, scarlett_sound, command = v
                    logger.warning(" msg: {}".format(msg))
                    logger.warning(
                        " scarlett_sound: {}".format(scarlett_sound))
                    logger.warning(" command: {}".format(command))
                    # NOTE: Create something like test_gdbus_player.ScarlettPlayer('pi-listening')
                    # NOTE: test_gdbus_player.ScarlettPlayer
                    # NOTE: self.bucket.put()
                    # NOTE: ADD self.queue.put(v)

        # with SessionBus() as bus:
        bus = SessionBus()
        ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')

        # SttFailedSignal / player_cb
        self.ss_failed_signal = bus.con.signal_subscribe(None,
                                                         "org.scarlett.Listener",
                                                         "SttFailedSignal",
                                                         '/org/scarlett/Listener',
                                                         None,
                                                         0,
                                                         player_cb)

        # ListenerReadySignal / player_cb
        self.ss_rdy_signal = bus.con.signal_subscribe(None,
                                                      "org.scarlett.Listener",
                                                      "ListenerReadySignal",
                                                      '/org/scarlett/Listener',
                                                      None,
                                                      0,
                                                      player_cb)

        # KeywordRecognizedSignal / player_cb
        self.ss_kw_rec_signal = bus.con.signal_subscribe(None,
                                                         "org.scarlett.Listener",
                                                         "KeywordRecognizedSignal",
                                                         '/org/scarlett/Listener',
                                                         None,
                                                         0,
                                                         player_cb)

        # CommandRecognizedSignal /command_cb
        self.ss_cmd_rec_signal = bus.con.signal_subscribe(None,
                                                          "org.scarlett.Listener",
                                                          "CommandRecognizedSignal",
                                                          '/org/scarlett/Listener',
                                                          None,
                                                          0,
                                                          command_cb)

        # ListenerCancelSignal / player_cb
        self.ss_cancel_signal = bus.con.signal_subscribe(None,
                                                         "org.scarlett.Listener",
                                                         "ListenerCancelSignal",
                                                         '/org/scarlett/Listener',
                                                         None,
                                                         0,
                                                         player_cb)

        # NOTE: print dir(ss)
        # NOTE: # Quit mainloop
        # NOTE: self.quit = ss.quit()

        # NOTE: # let listener know when we connect to it
        # NOTE: self._tasker_connected = ss.emitConnectedToListener("{}".format(
        # NOTE:     self._tasker_connected(ScarlettTasker().__class__.__name__)))

        logger.debug("ss PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(ss)

        # self.mainloopthread = ExcThread(self.queue, self.loop)
        # self.mainloopthread.daemon = True
        # self.mainloopthread.start()

    # NOTE: WE NEED TO ADD MORE TO THIS. WE NEED TO DO A self.queue.get() then have it join the mainthread
    # queue.get should have either a ScarlettPlayer or a ScarlettSpeaker object
    @trace
    def go(self):
        self.loop.run()

    @trace
    def run(self):
        try:
            print "ScarlettTasker Thread Started", self
            self.loop.run()
        except Exception:
            self.bucket.put(sys.exc_info())
            raise

# REGULAR OBJECT, not extending threading
# class ScarlettTasker():
#
#     @trace
#     def __init__(self):
#         self.loop = GLib.MainLoop()
#         self.queue = Queue.Queue(10)
#
#         @trace
#         def wait_for_t(t):
#             if not t.is_alive():
#                 # This won't block, since the thread isn't alive anymore
#                 t.join()
#                 print 'waiting.....'
#                 # Do whatever else you would do when join()
#                 # (or maybe collega_GUI?) returns
#             else:
#                 GLib.timeout_add(200, wait_for_t, t)
#
#         # NOTE: enumerate req to iterate through tuple and find GVariant
#         @trace
#         def player_cb(*args, **kwargs):
#             if SCARLETT_DEBUG:
#                 logger.debug("player_cb PrettyPrinter: ")
#                 pp = pprint.PrettyPrinter(indent=4)
#                 pp.pprint(args)
#             for i, v in enumerate(args):
#                 if SCARLETT_DEBUG:
#                     logger.debug("Type v: {}".format(type(v)))
#                     logger.debug("Type i: {}".format(type(i)))
#                 if type(v) is gi.overrides.GLib.Variant:
#                     if SCARLETT_DEBUG:
#                         logger.debug(
#                             "THIS SHOULD BE A Tuple now: {}".format(v))
#                     msg, scarlett_sound = v
#                     logger.warning(" msg: {}".format(msg))
#                     logger.warning(
#                         " scarlett_sound: {}".format(scarlett_sound))
#                     # NOTE: ADD self.queue.put(v)
#
#         # NOTE: enumerate req to iterate through tuple and find GVariant
#         @trace
#         def command_cb(*args, **kwargs):
#             if SCARLETT_DEBUG:
#                 logger.debug("player_cb PrettyPrinter: ")
#                 pp = pprint.PrettyPrinter(indent=4)
#                 pp.pprint(args)
#             for i, v in enumerate(args):
#                 if SCARLETT_DEBUG:
#                     logger.debug("Type v: {}".format(type(v)))
#                     logger.debug("Type i: {}".format(type(i)))
#                 if type(v) is gi.overrides.GLib.Variant:
#                     if SCARLETT_DEBUG:
#                         logger.debug(
#                             "THIS SHOULD BE A Tuple now: {}".format(v))
#                     msg, scarlett_sound, command = v
#                     logger.warning(" msg: {}".format(msg))
#                     logger.warning(
#                         " scarlett_sound: {}".format(scarlett_sound))
#                     logger.warning(" command: {}".format(command))
#                     # NOTE: ADD self.queue.put(v)
#
#         # with SessionBus() as bus:
#         bus = SessionBus()
#         ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')
#
#         # SttFailedSignal / player_cb
#         self.ss_failed_signal = bus.con.signal_subscribe(None,
#                                                          "org.scarlett.Listener",
#                                                          "SttFailedSignal",
#                                                          '/org/scarlett/Listener',
#                                                          None,
#                                                          0,
#                                                          player_cb)
#
#         # ListenerReadySignal / player_cb
#         self.ss_rdy_signal = bus.con.signal_subscribe(None,
#                                                       "org.scarlett.Listener",
#                                                       "ListenerReadySignal",
#                                                       '/org/scarlett/Listener',
#                                                       None,
#                                                       0,
#                                                       player_cb)
#
#         # KeywordRecognizedSignal / player_cb
#         self.ss_kw_rec_signal = bus.con.signal_subscribe(None,
#                                                          "org.scarlett.Listener",
#                                                          "KeywordRecognizedSignal",
#                                                          '/org/scarlett/Listener',
#                                                          None,
#                                                          0,
#                                                          player_cb)
#
#         # CommandRecognizedSignal /command_cb
#         self.ss_cmd_rec_signal = bus.con.signal_subscribe(None,
#                                                           "org.scarlett.Listener",
#                                                           "CommandRecognizedSignal",
#                                                           '/org/scarlett/Listener',
#                                                           None,
#                                                           0,
#                                                           command_cb)
#
#         # ListenerCancelSignal / player_cb
#         self.ss_cancel_signal = bus.con.signal_subscribe(None,
#                                                          "org.scarlett.Listener",
#                                                          "ListenerCancelSignal",
#                                                          '/org/scarlett/Listener',
#                                                          None,
#                                                          0,
#                                                          player_cb)
#
#         # Quit mainloop
#         self.quit = ss.quit()
#
#         # let listener know when we connect to it
#         self._tasker_connected = ss.emitConnectedToListener("{}".format(
#             self._tasker_connected(ScarlettTasker().__class__.__name__)))
#
#         logger.debug("ss PrettyPrinter: ")
#         pp = pprint.PrettyPrinter(indent=4)
#         pp.pprint(ss)
#
#         self.mainloopthread = ExcThread(self.queue, self.loop)
#         self.mainloopthread.daemon = True
#         self.mainloopthread.start()
#
#     # NOTE: WE NEED TO ADD MORE TO THIS. WE NEED TO DO A self.queue.get() then have it join the mainthread
#     # queue.get should have either a ScarlettPlayer or a ScarlettSpeaker object
#     @trace
#     def go(self):
#         self.loop.run()
#
#     @trace
#     def run(self):
#         logger.debug(
#             "{}".format(self._tasker_connected(ScarlettTasker().__class__.__name__)))


@trace
def main():
    """
    Parent thread and supervisor.
    """
    bucket = Queue.Queue()
    mainloop = GLib.MainLoop()

    # TODO: Try calling child thread like below.
    # TODO: Allow us to pass in a target, and args.
    # TODO: Eg. target=ScarlettPlayer or target=ScarlettSpeaker
    # SOURCE: https://github.com/jhcepas/npr/blob/master/nprlib/interface.py
    # t = ExcThread(bucket=exceptions, target=func, args=[args])
    # Start child thread
    thread_obj = ScarlettTasker(bucket, mainloop)
    thread_obj.daemon = True
    thread_obj.start()

    while True:
        try:
            exc = bucket.get(block=False)
            # NOTE: IMPORTANT NOTES
            # check type of exc
            # if exc is a ScarlettPlayer or a ScarlettSpeaker ...
            # s_obj = ScarlettPlayer
            # OR
            # s_obj = ScarlettSpeaker
            # add to the thread supervisor, which will block till finished
            # thread_obj.join(s_obj)
        except Queue.Empty:
            time.sleep(.2)
            logger.info('nothing yet')
            pass
        else:
            exc_type, exc_obj, exc_trace = exc
            # deal with the exception
            # print exc_type, exc_obj
            # print exc_trace
            # deal with the exception
            # print exc_trace, exc_type, exc_obj
            raise exc_obj

        thread_obj.join(0.1)
        if thread_obj.isAlive():
            continue
        else:
            break


if __name__ == '__main__':
    main()
