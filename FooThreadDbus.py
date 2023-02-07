#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# Refactored by Malcolm Jones to work with GTK+3 PyGobject( aka PyGI ).
# Mar 2016.

# ScarlettTasker application showing how once can combine the python
# threading module with GObject signals to make a simple thread
# manager class which can be used to stop horrible blocking GUIs.
#
# (c) 2008, John Stowers <john.stowers@gmail.com>
#
# This program serves as an example, and can be freely used, copied, derived
# and redistributed by anyone. No warranty is implied or given.

import os
import sys
import time

_INSTANCE = None

SCARLETT_DEBUG = True

# Prevents player or command callbacks from running multiple times
player_run = False
command_run = False

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
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import GObject
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import Gtk
import threading

GObject.threads_init()
Gst.init(None)

import time
import random

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

from gettext import gettext as _

import traceback
from functools import wraps
import Queue
from random import randint
from pydbus import SessionBus

import test_gdbus_speaker
import test_gdbus_player

###################################################################################################
# Audio Utils Start
###################################################################################################


def calculate_duration(num_samples, sample_rate):
    """Determine duration of samples using GStreamer helper for precise
    math."""
    return Gst.util_uint64_scale(num_samples, Gst.SECOND, sample_rate)


def create_buffer(data, timestamp=None, duration=None):
    """Create a new GStreamer buffer based on provided data.

    Mainly intended to keep gst imports out of non-audio modules.

    .. versionchanged:: 2.0
        ``capabilites`` argument was removed.
    """
    if not data:
        raise ValueError('Cannot create buffer without data')
    buffer_ = Gst.Buffer.new_wrapped(data)
    if timestamp is not None:
        buffer_.pts = timestamp
    if duration is not None:
        buffer_.duration = duration
    return buffer_


def millisecond_to_clocktime(value):
    """Convert a millisecond time to internal GStreamer time."""
    return value * Gst.MSECOND


def clocktime_to_millisecond(value):
    """Convert an internal GStreamer time to millisecond time."""
    return value // Gst.MSECOND

###################################################################################################
# Audio Utils End
###################################################################################################


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


# source: https://github.com/hpcgam/dicomimport/blob/1f265b1a5c9e631a536333633893ab525da87f16/doc-dcm/SAMPLEZ/nostaples/utils/scanning.py # NOQA
def abort_on_exception(func):
    """
    This function decorator wraps the run() method of a thread
    so that any exceptions in that thread will be logged and
    cause the threads 'abort' signal to be emitted with the exception
    as an argument.  This way all exception handling can occur
    on the main thread.

    Note that the entire sys.exc_info() tuple is passed out, this
    allows the current traceback to be used in the other thread.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception, e:
            thread_object = args[0]
            exc_info = sys.exc_info()
            thread_object.log.error('Exception type %s: %s' % (e.__class__.__name__, e.message))
            thread_object.emit('aborted', exc_info)
    return wrapper

# Create a player
logger = setup_logger()


class _IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """

    # @trace
    def __init__(self):
        GObject.GObject.__init__(self)

    # @trace
    def emit(self, *args):
        GObject.idle_add(GObject.GObject.emit, self, *args)


class _FooThread(threading.Thread, _IdleObject):
    """
    Cancellable thread which uses gobject signals to return information
    to the GUI.
    """
    __gsignals__ = {
        "completed": (
            GObject.SignalFlags.RUN_LAST, None, []),
        "progress": (
            GObject.SignalFlags.RUN_LAST, None, [
                GObject.TYPE_FLOAT])  # percent complete
    }

    # @trace
    def __init__(self, *args):
        threading.Thread.__init__(self)
        _IdleObject.__init__(self)
        self.cancelled = False
        self.data = args[0]
        self.name = args[1]
        # TODO: Add one more option to pass in object ScarlettPlayer or
        # ScarlettSpeaker
        self.setName(f"{self.name}")
        self.event_do_exit = threading.Event()

        # test_gdbus_player.ScarlettPlayer('pi-listening')

        player = test_gdbus_player

        def signal_handler_in_thread():

            def function_calling_gtk(event, result):
                result.append(player.ScarlettPlayer('pi-listening'))
                event.set()

            event = threading.Event()
            result = []
            GLib.idle_add(function_calling_gtk, event, result)
            event.wait()
            toggle_button_is_active = result[0]
            print(toggle_button_is_active)

        # toggle_button = Gtk.ToggleButton()
        #
        # def signal_handler_in_thread():
        #
        #     def function_calling_gtk(event, result):
        #         result.append(toggle_button.get_active())
        #         event.set()
        #
        #     event = threading.Event()
        #     result = []
        #     GLib.idle_add(function_calling_gtk, event, result)
        #     event.wait()
        #     toggle_button_is_active = result[0]
        #     print(toggle_button_is_active)

    # @trace
    def cancel(self):
        """
        Threads in python are not cancellable, so we implement our own
        cancellation logic
        """
        self.cancelled = True

    # @trace
    def run(self):
        print "Running %s" % str(self)
        for i in range(self.data):
            if self.cancelled:
                break
            time.sleep(0.1)
            self.emit("progress", i / float(self.data) * 100)
        self.emit("completed")


class FooThreadManager:
    """
    Manages many FooThreads. This involves starting and stopping
    said threads, and respecting a maximum num of concurrent threads limit
    """

    # @trace
    def __init__(self, maxConcurrentThreads):
        self.maxConcurrentThreads = maxConcurrentThreads
        # stores all threads, running or stopped
        self.fooThreads = {}
        # the pending thread args are used as an index for the stopped threads
        self.pendingFooThreadArgs = []

    # @trace
    def _register_thread_completed(self, thread, *args):
        """
        Decrements the count of concurrent threads and starts any
        pending threads if there is space
        """
        del(self.fooThreads[args])
        running = len(self.fooThreads) - len(self.pendingFooThreadArgs)

        print "%s completed. %s running, %s pending" % (
            thread, running, len(self.pendingFooThreadArgs))

        if running < self.maxConcurrentThreads:
            try:
                args = self.pendingFooThreadArgs.pop()
                print "Starting pending %s" % self.fooThreads[args]
                self.fooThreads[args].start()
            except IndexError:
                pass

    # @trace
    def make_thread(self, completedCb, progressCb, userData, *args):
        """
        Makes a thread with args. The thread will be started when there is
        a free slot
        """
        running = len(self.fooThreads) - len(self.pendingFooThreadArgs)

        if args not in self.fooThreads:
            thread = _FooThread(*args)
            # signals run in the order connected. Connect the user completed
            # callback first incase they wish to do something
            # before we delete the thread
            thread.connect("completed", completedCb, userData)
            thread.connect("completed", self._register_thread_completed, *args)
            thread.connect("progress", progressCb, userData)
            # This is why we use args, not kwargs, because args are hashable
            self.fooThreads[args] = thread

            if running < self.maxConcurrentThreads:
                print "Starting %s" % thread
                self.fooThreads[args].start()
            else:
                print "Queing %s" % thread
                self.pendingFooThreadArgs.append(args)

    # @trace
    def stop_all_threads(self, block=False):
        """
        Stops all threads. If block is True then actually wait for the thread
        to finish (may block the UI)
        """
        for thread in self.fooThreads.values():
            thread.cancel()
            if block and thread.isAlive():
                thread.join()


class ScarlettTasker(_IdleObject):

    # @trace
    def __init__(self, *args):
        _IdleObject.__init__(self)

        self.bucket = bucket = Queue.Queue()  # NOQA
        self.loop = GLib.MainLoop()
        self.hello = None

        # with SessionBus() as bus:
        bus = SessionBus()
        ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')  # NOQA

        # # SttFailedSignal / player_cb
        # ss_failed_signal = bus.con.signal_subscribe(None,  # NOQA
        #                                             "org.scarlett.Listener",
        #                                             "SttFailedSignal",
        #                                             '/org/scarlett/Listener',
        #                                             None,
        #                                             0,
        #                                             player_cb)
        ss_failed_signal = ss.SttFailedSignal.connect(player_cb)

        # # ListenerReadySignal / player_cb
        # ss_rdy_signal = bus.con.signal_subscribe(None,  # NOQA
        #                                          "org.scarlett.Listener",
        #                                          "ListenerReadySignal",
        #                                          '/org/scarlett/Listener',
        #                                          None,
        #                                          0,
        #                                          player_cb)
        ss_rdy_signal = ss.ListenerReadySignal.connect(player_cb)

        # # KeywordRecognizedSignal / player_cb
        # ss_kw_rec_signal = bus.con.signal_subscribe(None,  # NOQA
        #                                             "org.scarlett.Listener",
        #                                             "KeywordRecognizedSignal",
        #                                             '/org/scarlett/Listener',
        #                                             None,
        #                                             0,
        #                                             player_cb)
        ss_kw_rec_signal = ss.KeywordRecognizedSignal.connect(player_cb)

        # # CommandRecognizedSignal /command_cb
        # ss_cmd_rec_signal = bus.con.signal_subscribe(None,  # NOQA
        #                                              "org.scarlett.Listener",
        #                                              "CommandRecognizedSignal",
        #                                              '/org/scarlett/Listener',
        #                                              None,
        #                                              0,
        #                                              command_cb)
        ss_cmd_rec_signal = ss.CommandRecognizedSignal.connect(command_cb)

        # # ListenerCancelSignal / player_cb
        # # signal_subscribe (sender, interface_name, member, object_path, arg0, flags, callback, *user_data)
        # ss_cancel_signal = bus.con.signal_subscribe(None,  # NOQA
        #                                             "org.scarlett.Listener",
        #                                             "ListenerCancelSignal",
        #                                             '/org/scarlett/Listener',
        #                                             None,
        #                                             0,
        #                                             player_cb)
        ss_cancel_signal = ss.ListenerCancelSignal.connect(player_cb)

        ss.emitConnectedToListener('ScarlettTasker')

        # THE ACTUAL THREAD BIT
        self.manager = FooThreadManager(3)

        try:
            print "ScarlettTasker Thread Started", self
            self.loop.run()
        except Exception:
            ss_failed_signal.disconnect()
            ss_rdy_signal.disconnect()
            ss_kw_rec_signal.disconnect()
            ss_cmd_rec_signal.disconnect()
            ss_cancel_signal.disconnect()
            self.bucket.put(sys.exc_info())
            raise

    # @trace
    def quit(self, sender, event):
        self.manager.stop_all_threads(block=True)
        self.loop.quit()

    # @trace
    def stop_threads(self, *args):
        # THE ACTUAL THREAD BIT
        self.manager.stop_all_threads()

    # @trace
    def add_thread(self, sender):
        # make a thread and start it
        data = random.randint(20, 60)
        name = f"Thread #{random.randint(0, 1000)}"
        # rowref = self.pendingModel.insert(0, (name, 0))
        rowref = 'rowref userData'

        # THE ACTUAL THREAD BIT
        # def make_thread(self, completedCb, progressCb, userData, *args):
        self.manager.make_thread(
            self.thread_finished,
            self.thread_progress,
            rowref, data, name)

    # @trace
    def thread_finished(self, thread, rowref):
        pass
        # log
        # logger.info("thread: " + thread)
        # logger.info("rowref: " + rowref)
        # self.pendingModel.remove(rowref)
        # self.completeModel.insert(0, (thread.name,))

    # @trace
    def thread_progress(self, thread, progress, rowref):
        pass
        # self.pendingModel.set_value(rowref, 1, int(progress))


def print_keyword_args(**kwargs):
    # kwargs is a dict of the keyword args passed to the function
    for key, value in kwargs.iteritems():
        print "%s = %s" % (key, value)


# NOTE: enumerate req to iterate through tuple and find GVariant
# @trace
def player_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("player_cb PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(args)
        # MAR 13 2016
        logger.debug("player_cb kwargs")
        print_keyword_args(**kwargs)
    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug(f"Type v: {type(v)}")
            logger.debug(f"Type i: {type(i)}")
        if type(v) is gi.overrides.GLib.Variant:
            if SCARLETT_DEBUG:
                logger.debug(f"THIS SHOULD BE A Tuple now: {v}")
            msg, scarlett_sound = v
            logger.warning(f" msg: {msg}")
            logger.warning(f" scarlett_sound: {scarlett_sound}")
            if player_run := True:
                test_gdbus_player.ScarlettPlayer(scarlett_sound)
                player_run = False
            # NOTE: Create something like test_gdbus_player.ScarlettPlayer('pi-listening')
            # NOTE: test_gdbus_player.ScarlettPlayer
            # NOTE: self.bucket.put()
            # NOTE: ADD self.queue.put(v)


# NOTE: enumerate req to iterate through tuple and find GVariant
# @trace
def command_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("command_cb PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(args)
        # MAR 13 2016
        logger.debug("command_cb kwargs")
        print_keyword_args(**kwargs)
    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug(f"Type v: {type(v)}")
            logger.debug(f"Type i: {type(i)}")
        if type(v) is gi.overrides.GLib.Variant:
            if SCARLETT_DEBUG:
                logger.debug(f"THIS SHOULD BE A Tuple now: {v}")
            msg, scarlett_sound, command = v
            logger.warning(f" msg: {msg}")
            logger.warning(f" scarlett_sound: {scarlett_sound}")
            logger.warning(f" command: {command}")
            if command_run := True:
                test_gdbus_speaker.ScarlettSpeaker('Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands')  # NOQA
                command_run = False
            # NOTE: Create something like test_gdbus_player.ScarlettPlayer('pi-listening')
            # NOTE: test_gdbus_player.ScarlettPlayer
            # NOTE: self.bucket.put()
            # NOTE: ADD self.queue.put(v)


if __name__ == "__main__":
    _INSTANCE = st = ScarlettTasker()
