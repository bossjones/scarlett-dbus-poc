#!/usr/bin/env python  # NOQA
# -*- coding: utf-8 -*-

"""Scarlett Listener Module."""

# NOTE: THIS IS THE CLASS THAT WILL BE REPLACING scarlett_speaker.py eventually.
# It is cleaner, more object oriented, and will allows us to run proper tests.
# Also threading.RLock() and threading.Semaphore() works correctly.

# There are a LOT of threads going on here, all of them managed by Gstreamer.
# If pyglet ever needs to run under a Python that doesn't have a GIL, some
# locks will need to be introduced to prevent concurrency catastrophes.
#
# At the moment, no locks are used because we assume only one thread is
# executing Python code at a time.  Some semaphores are used to block and wake
# up the main thread when needed, these are all instances of
# threading.Semaphore.  Note that these don't represent any kind of
# thread-safety.

from __future__ import with_statement
from __future__ import division

import sys
import os

os.environ[
    "GST_DEBUG_DUMP_DOT_DIR"] = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug"
os.putenv('GST_DEBUG_DUMP_DIR_DIR',
          '/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
import threading

GObject.threads_init()
Gst.init(None)

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

import argparse
import pprint
pp = pprint.PrettyPrinter(indent=4)

try:
    import queue
except ImportError:
    import Queue as queue

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


QUEUE_SIZE = 10
BUFFER_SIZE = 10
SENTINEL = '__GSTDEC_SENTINEL__'

import StringIO

import re
import ConfigParser
import signal


from IPython.core.debugger import Tracer  # NOQA
from IPython.core import ultratb

from gettext import gettext as _

import generator_utils
import generator_subprocess
import generator_player

import scarlett_config

import logging
logger = logging.getLogger('scarlettlogger')

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

SCARLETT_CANCEL = "pi-cancel"
SCARLETT_LISTENING = "pi-listening"
SCARLETT_RESPONSE = "pi-response"
SCARLETT_FAILED = "pi-response2"

gst = Gst


#################################################################
# Managing the Gobject main loop thread.
#################################################################

_shared_loop_thread = None
_loop_thread_lock = threading.RLock()


def get_loop_thread():
    """Get the shared main-loop thread."""
    global _shared_loop_thread
    with _loop_thread_lock:
        if not _shared_loop_thread:
            # Start a new thread.
            _shared_loop_thread = MainLoopThread()
            _shared_loop_thread.start()
        return _shared_loop_thread


class MainLoopThread(threading.Thread):
    """A daemon thread encapsulating a Gobject main loop."""

    def __init__(self):
        super(MainLoopThread, self).__init__()
        self.loop = GObject.MainLoop()
        self.daemon = True

    def run(self):
        self.loop.run()


#################################################################
# Managing the GLib main loop thread.
#################################################################

_glib_shared_loop_thread = None
_glib_loop_thread_lock = threading.RLock()


def glib_get_loop_thread():
    """Get the shared main-loop thread."""
    global _shared_loop_thread
    with _loop_thread_lock:
        if not _shared_loop_thread:
            # Start a new thread.
            _shared_loop_thread = MainLoopThread()
            _shared_loop_thread.start()
        return _shared_loop_thread


class GLibMainLoopThread(threading.Thread):
    """A daemon thread encapsulating a Gobject main loop."""

    def __init__(self):
        super(GLibMainLoopThread, self).__init__()
        self.loop = GLib.MainLoop()
        self.daemon = True

    def run(self):
        self.loop.run()


class Server(object):
    """PyDbus Server Object."""

    def __init__(self, bus, path):
        self.loop = GLib.MainLoop()
        self.dbus_stack = []
        self.pipelines_stack = []

        self._message = 'This is the DBusServer'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = False

        self._status_ready = "  ScarlettListener is ready"
        self._status_kw_match = "  ScarlettListener caught a keyword match"
        self._status_cmd_match = "  ScarlettListener caught a command match"
        self._status_stt_failed = "  ScarlettListener hit Max STT failures"
        self._status_cmd_start = "  ScarlettListener emitting start command"
        self._status_cmd_fin = "  ScarlettListener Emitting Command run finish"
        self._status_cmd_cancel = "  ScarlettListener cancel speech Recognition"

        if self.debug:
            # NOTE: For testing puposes, mainly when in public
            # so you dont have to keep yelling scarlett in front of strangers
            self.kw_to_find = ['yo', 'hello', 'man', 'children']
        else:
            self.kw_to_find = self.config.get('scarlett', 'keywords')

        self.dbus_stack.append(bus)
        self.dbus_stack.append(path)
        logger.debug("Inside self.dbus_stack")
        pp.pprint(self.dbus_stack)

        interface_info = Gio.DBusNodeInfo.new_for_xml(
            self.__doc__).interfaces[0]

        method_outargs = {}
        method_inargs = {}
        for method in interface_info.methods:
            method_outargs[
                method.name] = '(' + ''.join([arg.signature for arg in method.out_args]) + ')'
            method_inargs[method.name] = tuple(
                arg.signature for arg in method.in_args)

        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

        logger.debug("Inside self.method_inargs and self.method_outargs")
        logger.debug("Inside self.method_inargs")
        pp.pprint(self.method_inargs)
        logger.debug("Inside self.method_outargs")
        pp.pprint(self.method_outargs)

        bus.register_object(
            object_path=path, interface_info=interface_info, method_call_closure=self.on_method_call)

    def run(self):
        self.loop.run()

    def quit(self):
        p = self.pipelines_stack[0]
        p.set_state(Gst.State.NULL)
        self.loop.quit()

    def on_method_call(self,
                       connection,
                       sender,
                       object_path,
                       interface_name,
                       method_name,
                       parameters,
                       invocation):

        args = list(parameters.unpack())
        for i, sig in enumerate(self.method_inargs[method_name]):
            # if UNIX_FD
            if sig is 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        if type(result) is list:
            result = tuple(result)
        elif not type(result) is tuple:
            result = (result,)

        out_args = self.method_outargs[method_name]
        if out_args != '()':
            logger.debug("Inside out_args in != ()")
            pp.pprint(out_args)
            logger.debug("Inside result != ()")
            pp.pprint(result)
            invocation.return_value(GLib.Variant(out_args, result))


class ScarlettListener(object):
    """Scarlett Listener Class."""

    def __init__(self, text_to_speak="", wavpath=""):
        """ScarlettListener object. Anything defined here belongs to the INSTANCE of the class."""
        #####################################
        #
        # # Set up the queue for data and run the main thread.
        # self.queue = queue.Queue(QUEUE_SIZE)
        # self.thread = get_loop_thread()
        #
        # # This wil get filled with an exception if opening fails.
        # self.read_exc = None
        # self.dot_exc = None
        #
        # # Return as soon as the stream is ready!
        # self.running = True
        # self.got_caps = False
        # self.pipeline.set_state(Gst.State.PLAYING)
        # self.on_debug_activate()
        # self.ready_sem.acquire()
        #
        # if self.read_exc:
        #     # An error occurred before the stream became ready.
        #     self.close(True)
        #     raise self.read_exc
        #####################################
        self._wavefile = []
        self._pitch = 75
        self._speed = 175
        self._wavpath = wavpath
        self._wavefile.append(self._wavpath)
        self._voice = "en+f3"
        self._text = _('{}'.format(text_to_speak))
        self._word_gap = 1
        self._command = ["espeak", "-p%s" % self._pitch,
                         "-s%s" % self._speed, "-g%s" % self._word_gap,
                         "-w", self._wavpath, "-v%s" % self._voice,
                         ".   %s   ." % self._text]

        # Write espeak data
        with generator_utils.time_logger('Espeak Subprocess To File'):
            self.running = True
            self.finished = False
            self.res = generator_subprocess.Subprocess(
                self._command, name='speaker_tmp', fork=False).run()
            generator_subprocess.check_pid(int(self.res))
            print "Did is run successfully? {}".format(self.res)

        # Have Gstreamer play it
        for path in self._wavefile:
            path = os.path.abspath(os.path.expanduser(path))
            with generator_player.ScarlettPlayer(path) as f:
                print(f.channels)
                print(f.samplerate)
                print(f.duration)
                for s in f:
                    pass

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True

    def __del__(self):
        """Garbage Collection, delete Speaker after using it."""
        self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """If something goes wrong, close class, then return exceptions."""
        self.close()
        return False

# Smoke test.
if __name__ == '__main__':
    tts_list = [
        'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    for scarlett_text in tts_list:
        with generator_utils.time_logger('Scarlett Speaks'):
            ScarlettListener(text_to_speak=scarlett_text,
                             wavpath="/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav")
