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
from generator_utils import trace
# import generator_subprocess
# import generator_player

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

SCARLETT_LISTENER_I_SIGNALS = {
    "completed": (
        GObject.SignalFlags.RUN_LAST, None, []),
    "progress": (
        GObject.SignalFlags.RUN_LAST, None, [
            GObject.TYPE_FLOAT]),  # percent complete
    "eos": (GObject.SignalFlags.RUN_LAST, None, ()),
    "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "died": (GObject.SignalFlags.RUN_LAST, None, ()),
    "async-done": (GObject.SignalFlags.RUN_LAST, None, ()),
    "state-change": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_INT)),
    # FIXME: AUDIT THE RETURN TYPES
    "bitrate-changed": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_INT)),
    "keyword-recgonized": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "command-recgonized": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "stt-failed": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "listener-cancel": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "listener-ready": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "connected-to-server": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "listener-message": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    'finished': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    'aborted': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
}


class PlayerType:
    """Enum of Player Types."""
    SCARLETT_CANCEL = "pi-cancel"
    SCARLETT_LISTENING = "pi-listening"
    SCARLETT_RESPONSE = "pi-response"
    SCARLETT_FAILED = "pi-response2"

gst = Gst
HERE = os.path.dirname(__file__)

# Pocketsphinx defaults

LANGUAGE_VERSION = 1473
HOMEDIR = "/home/pi"
LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm".format(
    HOMEDIR)
DICT_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict".format(
    HOMEDIR)
LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
DICT_PATH = "{}/{}.dic".format(DICT_FILE_HOME, LANGUAGE_VERSION)
HMM_PATH = "{}/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us".format(
    HOMEDIR)
bestpath = 0
PS_DEVICE = 'plughw:CARD=Device,DEV=0'


# source: https://github.com/hpcgam/dicomimport/blob/1f265b1a5c9e631a536333633893ab525da87f16/doc-dcm/SAMPLEZ/nostaples/utils/scanning.py  # NOQA
def abort_on_exception(func):  # NOQA
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


class _IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """

    @trace
    def __init__(self):
        GObject.GObject.__init__(self)

    @trace
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

    @trace
    def __init__(self, *args):
        threading.Thread.__init__(self)
        _IdleObject.__init__(self)
        self.cancelled = False
        self.data = args[0]
        self.name = args[1]
        self.setName("%s" % self.name)

    @trace
    def cancel(self):
        """
        Threads in python are not cancellable, so we implement our own
        cancellation logic
        """
        self.cancelled = True

    @trace
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

    @trace
    def __init__(self, maxConcurrentThreads):
        self.maxConcurrentThreads = maxConcurrentThreads
        # stores all threads, running or stopped
        self.fooThreads = {}
        # the pending thread args are used as an index for the stopped threads
        self.pendingFooThreadArgs = []

    @trace
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

    @trace
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

    @trace
    def stop_all_threads(self, block=False):
        """
        Stops all threads. If block is True then actually wait for the thread
        to finish (may block the UI)
        """
        for thread in self.fooThreads.values():
            thread.cancel()
            if block:
                if thread.isAlive():
                    thread.join()


class Server(object):
    """PyDbus Server Object."""

    def __init__(self, bus, path):
        self.loop = GObject.MainLoop()
        method_outargs = {}
        method_inargs = {}
        for interface in Gio.DBusNodeInfo.new_for_xml(self.__doc__).interfaces:

            for method in interface.methods:
                method_outargs[method.name] = '(' + ''.join([arg.signature for arg in method.out_args]) + ')'
                method_inargs[method.name] = tuple(arg.signature for arg in method.in_args)

            bus.register_object(object_path=path,
                                interface_info=interface,
                                method_call_closure=self.on_method_call)

        self.method_inargs = method_inargs
        self.method_outargs = method_outargs

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
            if sig is 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        # out_args is atleast (signature1). We therefore always wrap the result
        # as a tuple. Refer to https://bugzilla.gnome.org/show_bug.cgi?id=765603
        result = (result,)

        out_args = self.method_outargs[method_name]
        if out_args != '()':
            variant = GLib.Variant(out_args, result)
            invocation.return_value(variant)
        else:
            invocation.return_value(None)

# OLD WAY OF STARTING THIS SERVER #    def __init__(self, bus, path):
# OLD WAY OF STARTING THIS SERVER #        self.loop = GObject.MainLoop()
        # # self.loop = get_loop_thread()
        # self.dbus_stack = []
        # self.pipelines_stack = []
        # self.elements_stack = []
        #
        # self._message = 'This is the DBusServer'
        # self.config = scarlett_config.Config()
        # self.override_parse = ''
        # self.failed = 0
        # self.kw_found = 0
        # self.debug = False
        # self.create_dot = True
        # self.terminate = False
        #
        # self.capsfilter_queue_overrun_handler = None
        #
        # # # Thread manager, maximum of 1 since it'll be long running
        # # self.manager = FooThreadManager(1)
        #
        # self._status_ready = "  ScarlettListener is ready"
        # self._status_kw_match = "  ScarlettListener caught a keyword match"
        # self._status_cmd_match = "  ScarlettListener caught a command match"
        # self._status_stt_failed = "  ScarlettListener hit Max STT failures"
        # self._status_cmd_start = "  ScarlettListener emitting start command"
        # self._status_cmd_fin = "  ScarlettListener Emitting Command run finish"
        # self._status_cmd_cancel = "  ScarlettListener cancel speech Recognition"
        #
        # if self.debug:
        #     # NOTE: For testing puposes, mainly when in public
        #     # so you dont have to keep yelling scarlett in front of strangers
        #     self.kw_to_find = ['yo', 'hello', 'man', 'children']
        # else:
        #     self.kw_to_find = self.config.get('scarlett', 'keywords')
        #
        # self.dbus_stack.append(bus)
        # self.dbus_stack.append(path)
        # logger.debug("Inside self.dbus_stack")
        # pp.pprint(self.dbus_stack)

# OLD WAY OF STARTING THIS SERVER #        method_outargs = {}
# OLD WAY OF STARTING THIS SERVER #        method_inargs = {}
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #        interface_info = Gio.DBusNodeInfo.new_for_xml(
# OLD WAY OF STARTING THIS SERVER #            self.__doc__).interfaces[0]
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #        for method in interface_info.methods:
# OLD WAY OF STARTING THIS SERVER #            method_outargs[
# OLD WAY OF STARTING THIS SERVER #                method.name] = '(' + ''.join([arg.signature for arg in method.out_args]) + ')'
# OLD WAY OF STARTING THIS SERVER #            method_inargs[method.name] = tuple(
# OLD WAY OF STARTING THIS SERVER #                arg.signature for arg in method.in_args)
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #        self.method_inargs = method_inargs
# OLD WAY OF STARTING THIS SERVER #        self.method_outargs = method_outargs
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #        logger.debug("Inside self.method_inargs and self.method_outargs")
# OLD WAY OF STARTING THIS SERVER #        logger.debug("Inside self.method_inargs")
# OLD WAY OF STARTING THIS SERVER #        pp.pprint(self.method_inargs)
# OLD WAY OF STARTING THIS SERVER #        logger.debug("Inside self.method_outargs")
# OLD WAY OF STARTING THIS SERVER #        pp.pprint(self.method_outargs)
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #        bus.register_object(
# OLD WAY OF STARTING THIS SERVER #            object_path=path, interface_info=interface_info, method_call_closure=self.on_method_call)

    ##############################################################
    # threading related functions START
    ##############################################################
    # @trace
    # def stop_threads(self, *args):
    #     # THE ACTUAL THREAD BIT
    #     self.manager.stop_all_threads()
    #
    # @trace
    # def add_thread(self, sender):
    #     # make a thread and start it
    #     data = random.randint(20, 60)
    #     name = "Thread #%s" % random.randint(0, 1000)
    #     rowref = self.pendingModel.insert(0, (name, 0))
    #
    #     # THE ACTUAL THREAD BIT
    #     self.manager.make_thread(
    #         self.thread_finished,
    #         self.thread_progress,
    #         rowref, data, name)
    #
    # @trace
    # def thread_finished(self, thread, rowref):
    #     self.pendingModel.remove(rowref)
    #     self.completeModel.insert(0, (thread.name,))
    #
    # @trace
    # def thread_progress(self, thread, progress, rowref):
    #     self.pendingModel.set_value(rowref, 1, int(progress))

    ##############################################################
    # threading related functions END
    ##############################################################

    def run(self):
        self.loop.run()

    # NOTE: quit needs to look like this
    # @trace
    # def quit(self, sender, event):
    #     self.manager.stop_all_threads(block=True)
    #     Gtk.main_quit()

    def quit(self):
        """quit method with ONLY dbus functionality."""
        self.loop.quit()

    # def quit(self):
    #     """quit method with pipeline functionality."""
    #     p = self.pipelines_stack[0]
    #     p.set_state(Gst.State.NULL)
    #     self.loop.quit()

# OLD WAY OF STARTING THIS SERVER #            def on_method_call(self,
# OLD WAY OF STARTING THIS SERVER #                               connection,
# OLD WAY OF STARTING THIS SERVER #                               sender,
# OLD WAY OF STARTING THIS SERVER #                               object_path,
# OLD WAY OF STARTING THIS SERVER #                               interface_name,
# OLD WAY OF STARTING THIS SERVER #                               method_name,
# OLD WAY OF STARTING THIS SERVER #                               parameters,
# OLD WAY OF STARTING THIS SERVER #                               invocation):
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #                args = list(parameters.unpack())
# OLD WAY OF STARTING THIS SERVER #                for i, sig in enumerate(self.method_inargs[method_name]):
# OLD WAY OF STARTING THIS SERVER #                    # if UNIX_FD
# OLD WAY OF STARTING THIS SERVER #                    if sig is 'h':
# OLD WAY OF STARTING THIS SERVER #                        msg = invocation.get_message()
# OLD WAY OF STARTING THIS SERVER #                        fd_list = msg.get_unix_fd_list()
# OLD WAY OF STARTING THIS SERVER #                        args[i] = fd_list.get(args[i])
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #                result = getattr(self, method_name)(*args)
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #                if type(result) is list:
# OLD WAY OF STARTING THIS SERVER #                    result = tuple(result)
# OLD WAY OF STARTING THIS SERVER #                elif not type(result) is tuple:
# OLD WAY OF STARTING THIS SERVER #                    result = (result,)
# OLD WAY OF STARTING THIS SERVER #
# OLD WAY OF STARTING THIS SERVER #                out_args = self.method_outargs[method_name]
# OLD WAY OF STARTING THIS SERVER #                if out_args != '()':
# OLD WAY OF STARTING THIS SERVER #                    logger.debug("Inside out_args in != ()")
# OLD WAY OF STARTING THIS SERVER #                    pp.pprint(out_args)
# OLD WAY OF STARTING THIS SERVER #                    logger.debug("Inside result != ()")
# OLD WAY OF STARTING THIS SERVER #                    pp.pprint(result)
# OLD WAY OF STARTING THIS SERVER #                    invocation.return_value(GLib.Variant(out_args, result))


class ScarlettListenerI(threading.Thread, _IdleObject):
    """
    Attempt to take out all Gstreamer logic and put it in a class ouside the dbus server.
    Cancellable thread which uses gobject signals to return information
    to the GUI.
    """
    __gsignals__ = SCARLETT_LISTENER_I_SIGNALS

    # SCARLETT_LISTENER_I_SIGNALS = {
    #     "completed": (
    #         GObject.SignalFlags.RUN_LAST, None, []),
    #     "progress": (
    #         GObject.SignalFlags.RUN_LAST, None, [
    #             GObject.TYPE_FLOAT]),  # percent complete
    #     "eos": (GObject.SignalFlags.RUN_LAST, None, ()),
    #     "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "died": (GObject.SignalFlags.RUN_LAST, None, ()),
    #     "async-done": (GObject.SignalFlags.RUN_LAST, None, ()),
    #     "state-change": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_INT)),
    #     # FIXME: AUDIT THE RETURN TYPES
    #     "keyword-recgonized": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "command-recgonized": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "stt-failed": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "listener-cancel": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "listener-ready": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "connected-to-server": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     "listener-message": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    #     'finished': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,)),
    #     'aborted': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,))
    # }

    @trace
    def __init__(self, *args):
        threading.Thread.__init__(self)
        _IdleObject.__init__(self)

        Gst.init(None)

        self.running = False
        self.finished = False
        self.ready_sem = threading.Semaphore(0)
        self.queue = queue.Queue(QUEUE_SIZE)

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        self.cancelled = False
        self.data = args[0]
        self.name = args[1]
        self.setName("%s" % self.name)

        self.pipelines_stack = []
        self.elements_stack = []
        self.gst_bus_stack = []

        self._message = 'This is the ScarlettListenerI'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = True
        self.terminate = False

        self.capsfilter_queue_overrun_handler = None

        # source: https://github.com/ljmljz/xpra/blob/b32f748e0c29cdbfab836b3901c1e318ea142b33/src/xpra/sound/sound_pipeline.py  # NOQA
        self.bus = None
        self.bus_message_element_handler_id = None
        self.bus_message_error_handler_id = None
        self.bus_message_eos_handler_id = None
        self.bus_message_state_changed_handler_id = None
        self.pipeline = None
        self.start_time = 0
        self.state = "stopped"
        self.buffer_count = 0
        self.byte_count = 0

        # # Thread manager, maximum of 1 since it'll be long running
        # self.manager = FooThreadManager(1)

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

        if self.read_exc:
            # An error occurred before the stream became ready.
            self.close(True)
            raise self.read_exc

    def connect_to_dbus(self):
        # self.dbus_stack.append(bus)
        # self.dbus_stack.append(path)
        # logger.debug("Inside self.dbus_stack")
        # pp.pprint(self.dbus_stack)
        pass

    def scarlett_reset_listen(self):
        self.failed = 0
        self.kw_found = 0

    def cancel_listening(self):
        logger.debug("Inside cancel_listening function")
        self.scarlett_reset_listen()
        logger.debug("self.failed = %i" % (self.failed))
        logger.debug(
            "self.keyword_identified = %i" %
            (self.kw_found))

    @trace
    def play(self):
        p = self.pipelines_stack[0]
        self.state = "active"
        self.running = True
        # GST_STATE_PAUSED is the state in which an element is ready to accept and handle data.
        # For most elements this state is the same as PLAYING. The only exception to this rule are sink elements.
        # Sink elements only accept one single buffer of data and then block.
        # At this point the pipeline is 'prerolled' and ready to render data immediately.
        p.set_state(Gst.State.PAUSED)
        # GST_STATE_PLAYING is the highest state that an element can be in.
        # For most elements this state is exactly the same as PAUSED,
        # they accept and process events and buffers with data.
        # Only sink elements need to differentiate between PAUSED and PLAYING state.
        # In PLAYING state, sink elements actually render incoming data,
        # e.g. output audio to a sound card or render video pictures to an image sink.
        ret = p.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("ERROR: Unable to set the pipeline to the playing state")
        self.on_debug_activate()
        logger.debug("BEFORE: self.ready_sem.acquire()")
        self.ready_sem.acquire()
        logger.debug("AFTER: self.ready_sem.acquire()")
        logger.info("Press Ctrl+C to quit ...")

    @trace
    def stop(self):
        p = self.pipelines_stack[0]
        self.state = "stopped"
        self.running = False
        # GST_STATE_NULL is the default state of an element.
        # In this state, it has not allocated any runtime resources,
        # it has not loaded any runtime libraries and it can obviously not handle data.
        p.set_state(Gst.State.NULL)

    def get_pocketsphinx_definition(self, device, hmm, lm, dic, override=False):
        """
        GST_DEBUG=2,pocketsphinx*:5 gst-launch-1.0 alsasrc device=plughw:CARD=Device,DEV=0 ! \
                                                    queue name=capsfilter_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    capsfilter caps='audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved' ! \
                                                    audioconvert ! \
                                                    audioresample ! \
                                                    pocketsphinx \
                                                    name=asr \
                                                    lm=~/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm/1473.lm \
                                                    dict=~/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict/1473.dic \
                                                    hmm=~/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us
                                                    bestpath=true ! \
                                                    tee name=tee ! \
                                                    queue name=appsink_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    appsink caps='audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved' \
                                                    drop=false max-buffers=10 sync=false \
                                                    emit-signals=true tee.
                                                    queue name=fakesink_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    fakesink sync=false
        """
        logger.debug("Inside get_pocketsphinx_definition")

        if override:
            _gst_launch = override
        else:
            _gst_launch = ['alsasrc device=' +
                           device,
                           # source: https://github.com/walterbender/story/blob/master/grecord.py
                           # without a buffer here, gstreamer struggles at the start of the
                           # recording and then the A/V sync is bad for the whole video
                           # (possibly a gstreamer/ALSA bug -- even if it gets caught up, it
                           # should be able to resync without problem)
                           'queue name=capsfilter_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           'capsfilter name=capsfilter caps=audio/x-raw,format=S16LE,channels=1,layout=interleaved',
                           'audioconvert name=audioconvert',
                           'audioresample name=audioresample',
                           'identity name=ident',
                           'pocketsphinx name=asr',
                           'tee name=tee',
                           'queue name=appsink_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           #  caps=audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved   # NOQA
                           'appsink name=appsink drop=false max-buffers=10 sync=false emit-signals=true tee.',
                           'queue leaky=2 name=fakesink_queue',
                           'fakesink']

        return _gst_launch

    @trace
    def cancel(self):
        """
        Threads in python are not cancellable, so we implement our own
        cancellation logic
        """
        self.cancelled = True

    @abort_on_exception
    def run(self, event):
        # TODO: WE NEED TO USE A THREADING EVENT OR A RLOCK HERE TO WAIT TILL DBUS SERVICE IS RUNNING TO CONNECT
        # TODO: SIGNALS TO THE DBUS PROXY METHODS WE WANT TO USE
        # TODO: lock.acquire()
        # TODO: self.connect_to_dbus()
        # TODO: self.setup_dbus_callbacks_handlers()
        # TODO: self.init_gst()
        print "Running %s" % str(self)
        self.play()
        self.emit('playback-status-changed')
        self.emit('playing-changed')
        # FIXME: is this needed? # self.mainloop.run()

    # NOTE: This function generates the dot file, checks that graphviz in installed and
    # then finally generates a png file, which it then displays
    def on_debug_activate(self):
        dotfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-listener.dot"
        pngfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-listener-pipeline.png"  # NOQA
        if os.access(dotfile, os.F_OK):
            os.remove(dotfile)
        if os.access(pngfile, os.F_OK):
            os.remove(pngfile)
        Gst.debug_bin_to_dot_file(self.pipelines_stack[0],
                                  Gst.DebugGraphDetails.ALL, "generator-listener")
        os.system('/usr/bin/dot' + " -Tpng -o " + pngfile + " " + dotfile)

    def result(self, final_hyp):
        """Forward result signals on the bus to the main thread."""
        logger.debug("Inside result function")
        logger.debug("final_hyp: {}".format(final_hyp))
        pp.pprint(final_hyp)
        logger.debug("kw_to_find: {}".format(self.kw_to_find))
        if final_hyp in self.kw_to_find:
            logger.debug(
                "HYP-IS-SOMETHING: " +
                final_hyp +
                "\n\n\n")
            self.failed = 0
            self.kw_found = 1
            self.emitKeywordRecognizedSignal()  # CHANGEME
        else:
            failed_temp = self.failed + 1
            self.failed = failed_temp
            logger.debug(
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.emitSttFailedSignal()  # CHANGEME
                self.scarlett_reset_listen()

    def run_cmd(self, final_hyp):
        logger.debug("Inside run_cmd function")
        logger.debug("KEYWORD IDENTIFIED BABY")
        logger.debug(
            "self.kw_found = %i" %
            (self.kw_found))
        if final_hyp == 'CANCEL':
            self.emitListenerCancelSignal()  # CHANGEME
            self.cancel_listening()
        else:
            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified
            self.emitCommandRecognizedSignal(final_hyp)  # CHANGEME
            logger.info(
                " Command = {}".format(final_hyp))
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def init_gst(self, device=None, hmm=None, lm=None, dict_ps=None):
        logger.debug("Inside init_gst")
        self.start_time = time.time()
        pipeline = Gst.parse_launch(' ! '.join(
                                    self.get_pocketsphinx_definition(device,
                                                                     hmm,
                                                                     lm,
                                                                     dict_ps)))
        logger.debug("After get_pocketsphinx_definition")
        # Add pipeline obj to stack we can pull from later
        self.pipelines_stack.append(pipeline)

        gst_bus = pipeline.get_bus()
        # gst_bus = pipeline.get_gst_bus()
        gst_bus.add_signal_watch()
        self.bus_message_element_handler_id = gst_bus.connect("message::element", self._on_message)
        self.bus_message_eos_handler_id = gst_bus.connect("message::eos", self._on_message)
        self.bus_message_error_handler_id = gst_bus.connect("message::error", self._on_message)
        self.bus_message_state_changed_handler_id = gst_bus.connect("message::state-changed", self._on_state_changed)

        # Add bus obj to stack we can pull from later
        self.gst_bus_stack(gst_bus)

        appsink = pipeline.get_by_name('appsink')
        appsink.set_property(
            'caps',
            Gst.Caps.from_string('audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved'),
        )

        appsink.set_property('drop', False)
        appsink.set_property('max-buffers', BUFFER_SIZE)
        appsink.set_property('sync', False)

        # The callback to receive decoded data.
        appsink.set_property('emit-signals', True)
        appsink.connect("new-sample", self._new_sample)

        self.caps_handler = appsink.get_static_pad("sink").connect(
            "notify::caps", self._notify_caps
        )

        self.elements_stack.append(appsink)

        # get gst pipeline element pocketsphinx and set properties
        pocketsphinx = pipeline.get_by_name('asr')
        if hmm:
            pocketsphinx.set_property('hmm', hmm)
        if lm:
            pocketsphinx.set_property('lm', lm)
        if dict_ps:
            pocketsphinx.set_property('dict', dict_ps)

        pocketsphinx.set_property('fwdflat', True)  # Enable Flat Lexicon Search | Default: true
        pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        pocketsphinx.set_property('dsratio', 1)  # Evaluate acoustic model every N frames |  Integer. Range: 1 - 10 Default: 1
        pocketsphinx.set_property('maxhmmpf', 3000)  # Maximum number of HMMs searched per frame | Integer. Range: 1 - 100000 Default: 30000
        pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        # pocketsphinx.set_property('maxwpf', -1)  # pocketsphinx.set_property('maxwpf', 20)  # Maximum number of words searched per frame | Range: 1 - 100000 Default: -1

        self.elements_stack.append(pocketsphinx)

        capsfilter_queue = pipeline.get_by_name('capsfilter_queue')
        capsfilter_queue.set_property('leaky', True)  # prefer fresh data
        capsfilter_queue.set_property('silent', False)
        capsfilter_queue.set_property('max-size-time', 0)  # 0 seconds
        capsfilter_queue.set_property('max-size-buffers', 0)
        capsfilter_queue.set_property('max-size-bytes', 0)
        self.capsfilter_queue_overrun_handler = capsfilter_queue.connect('overrun', self._log_queue_overrun)

        # capsfilter_queue.connect('overrun', self._on_overrun)
        # capsfilter_queue.connect('underrun', self._on_underrun)
        # capsfilter_queue.connect('pushing', self._on_pushing)
        # capsfilter_queue.connect('running', self._on_running)

        self.elements_stack.append(capsfilter_queue)

        ident = pipeline.get_by_name('ident')
        # ident.connect('handoff', self._on_handoff)

        self.elements_stack.append(ident)

        logger.debug("After all self.elements_stack.append() calls")
        # Set up the queue for data and run the main thread.
        self.queue = queue.Queue(QUEUE_SIZE)
        self.thread = get_loop_thread()

    def _on_handoff(self, element, buf):
        logger.debug('buf:')
        pp.pprint(buf)
        pp.pprint(dir(buf))
        logger.debug('on_handoff - %d bytes' % len(buf))
        # print 'buf =', buf
        # print 'dir(buf) =', dir(buf)

        if self.signed is None:
            # only ever one caps struct on our buffers
            struct = buf.get_caps().get_structure(0)

            # I think these are always set too, but catch just in case
            try:
                self.signed = struct["signed"]
                self.depth = struct["depth"]
                self.rate = struct["rate"]
                self.channels = struct["channels"]
            except:
                logger.debug('on_handoff: missing caps')
                pass

        # raw = str(buf)
        #
        # # print 'len(raw) =', len(raw)
        #
        # sm = 0
        # for i in range(0, len(raw)):
        #     sm += ord(raw[i])
        # # print sm
        # FIXEME: Add somthing like analyse.py
        # SOURCE: https://github.com/jcupitt/huebert/blob/master/huebert/audio.py

    def _on_state_changed(self, bus, msg):
        states = msg.parse_state_changed()
        # To state is PLAYING
        if msg.src.get_name() == "pipeline0" and states[1] == 4:
            logger.info('Inside pipeline0 on _on_state_changed')
            logger.info("State: {}".format(states[1]))
            self.ready_sem.release()
            return False
        else:
            logger.error('NOTHING RETURNED in _on_state_changed')
            logger.info("State: {}".format(states[1]))

    def _on_overrun(self, element):
        logging.debug('on_overrun')

    def _on_underrun(self, element):
        logging.debug('on_underrun')

    def _on_running(self, element):
        logging.debug('on_running')

    def _on_pushing(self, element):
        logging.debug('on_pushing')

    def _notify_caps(self, pad, args):
        """The callback for the sinkpad's "notify::caps" signal.
        """
        # The sink has started to receive data, so the stream is ready.
        # This also is our opportunity to read information about the
        # stream.
        self.got_caps = True

        # Allow constructor to complete.
        self.ready_sem.release()

    _got_a_pad = False

    def _log_queue_overrun(self, queue):
        cbuffers = queue.get_property('current-level-buffers')
        cbytes = queue.get_property('current-level-bytes')
        ctime = queue.get_property('current-level-time')

    def _new_sample(self, sink):
        """The callback for appsink's "new-sample" signal.
        """
        if self.running:
            # New data is available from the pipeline! Dump it into our
            # queue (or possibly block if we're full).
            buf = sink.emit('pull-sample').get_buffer()
            self.queue.put(buf.extract_dup(0, buf.get_size()))
        return Gst.FlowReturn.OK

    def _on_message(self, bus, message):
        """The callback for GstBus's "message" signal (for two kinds of
        messages).
        """
        # logger.debug("[_on_message](%s, %s)", bus, message)
        if not self.finished:
            struct = message.get_structure()

            if message.type == Gst.MessageType.EOS:
                # The file is done. Tell the consumer thread.
                self.queue.put(SENTINEL)
                if not self.got_caps:
                    logger.error(
                        "If the stream ends before _notify_caps was called, this is an invalid stream.")
                    # If the stream ends before _notify_caps was called, this
                    # is an invalid file.
                    self.read_exc = generator_utils.NoStreamError()
                    self.ready_sem.release()
            elif struct and struct.get_name() == 'pocketsphinx':
                        if struct['final']:
                            logger.info(struct['hypothesis'])
                            if self.kw_found == 1:
                                # If keyword is set AND qualifier
                                # then perform action
                                self.run_cmd(struct['hypothesis'])
                            else:
                                # If it's the main keyword,
                                # set values wait for qualifier
                                self.result(struct['hypothesis'])
            elif message.type == Gst.MessageType.ERROR:
                gerror, debug = message.parse_error()
                if 'not-linked' in debug:
                    logger.error('not-linked')
                    self.read_exc = generator_utils.NoStreamError()
                else:
                    logger.info("FileReadError")
                    self.read_exc = generator_utils.FileReadError(debug)
                self.ready_sem.release()

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True

            try:
                gst_bus = self.gst_bus_stack[0]
            except:
                logger.error("Failed to get gst_bus from gst_bus_stack[0]")
                pass

            if gst_bus:
                gst_bus.remove_signal_watch()
                if self.bus_message_element_handler_id:
                    gst_bus.disconnect(self.bus_message_element_handler_id)
                if self.bus_message_error_handler_id:
                    gst_bus.disconnect(self.bus_message_error_handler_id)
                if self.bus_message_eos_handler_id:
                    gst_bus.disconnect(self.bus_message_eos_handler_id)
                if self.bus_message_state_changed_handler_id:
                    gst_bus.disconnect(self.bus_message_state_changed_handler_id)

            self.bus = None
            self.pipeline = None
            self.codec = None
            self.bitrate = -1
            self.state = None

            # Unregister for signals, which we registered for above with
            # `add_signal_watch`. (Without this, GStreamer leaks file
            # descriptors.)
            logger.debug('BEFORE p = self.pipelines_stack[0]')
            p = self.pipelines_stack[0]
            p.get_bus().remove_signal_watch()
            logger.debug('AFTER p.get_bus().remove_signal_watch()')

            # Block spurious signals.
            appsink = self.elements_stack[0]
            appsink.get_static_pad("sink").disconnect(self.caps_handler)

            # Make space in the output queue to let the decoder thread
            # finish. (Otherwise, the thread blocks on its enqueue and
            # the interpreter hangs.)
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass

            # Halt the pipeline (closing file).
            self.stop()

            # Delete the pipeline object. This seems to be necessary on Python
            # 2, but not Python 3 for some reason: on 3.5, at least, the
            # pipeline gets dereferenced automatically.
            del p


class ScarlettListener(Server):  # NOQA
    '''
    <!DOCTYPE node PUBLIC '-//freedesktop//DTD D-BUS Object Introspection 1.0//EN'
    'http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd'>
    <node>
      <interface name='org.freedesktop.DBus.Introspectable'>
          <method name='Introspect'>
              <arg name='data' direction='out' type='s'/>
          </method>
      </interface>
      <interface name='org.freedesktop.DBus.Properties'>
          <method name='Get'>
              <arg name='interface' direction='in' type='s'/>
              <arg name='property' direction='in' type='s'/>
              <arg name='value' direction='out' type='v'/>
          </method>
          <method name="Set">
              <arg name="interface_name" direction="in" type="s"/>
              <arg name="property_name" direction="in" type="s"/>
              <arg name="value" direction="in" type="v"/>
          </method>
          <method name='GetAll'>
              <arg name='interface' direction='in' type='s'/>
              <arg name='properties' direction='out' type='a{sv}'/>
          </method>
      </interface>
      <interface name='org.scarlett.Listener1'>
        <method name='emitKeywordRecognizedSignal'>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitCommandRecognizedSignal'>
          <arg type='s' name='command' direction='in'/>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitSttFailedSignal'>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitListenerCancelSignal'>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitListenerReadySignal'>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitConnectedToListener'>
          <arg type='s' name='scarlett_plugin' direction='in'/>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='emitListenerMessage'>
          <arg type='s' name='s_cmd' direction='out'/>
        </method>
        <method name='quit'>
        </method>
        <property name='CanQuit' type='b' access='read' />
        <property name='Fullscreen' type='b' access='readwrite' />
        <property name='CanRaise' type='b' access='read' />
        <property name='HasTrackList' type='b' access='read'/>
        <property name='Identity' type='s' access='read'/>
        <property name='DesktopEntry' type='s' access='read'/>
        <signal name='KeywordRecognizedSignal'>
          <arg type='(ss)' name='kw_rec_status' direction='out'/>
        </signal>
        <signal name='CommandRecognizedSignal'>
          <arg type='(sss)' name='cmd_rec_status' direction='out'/>
        </signal>
        <signal name='SttFailedSignal'>
          <arg type='(ss)' name='stt_failed_status' direction='out'/>
        </signal>
        <signal name='ListenerCancelSignal'>
          <arg type='(ss)' name='listener_cancel_status' direction='out'/>
        </signal>
        <signal name='ListenerReadySignal'>
          <arg type='(ss)' name='listener_rdy_status' direction='out'/>
        </signal>
        <signal name='ConnectedToListener'>
          <arg type='s' name='conn_to_lis_status' direction='out'/>
        </signal>
      </interface>
    </node>
    '''

    LISTENER_IFACE = 'org.scarlett.Listener'
    LISTENER_PLAYER_IFACE = 'org.scarlett.Listener.Player'
    LISTENER_TRACKLIST_IFACE = 'org.scarlett.Listener.TrackList'
    LISTENER_PLAYLISTS_IFACE = 'org.scarlett.Listener.Playlists'
    LISTENER_EVENTS_IFACE = 'org.scarlett.Listener.event'

    # def __repr__(self):
    #     return '<ScarlettListener>'

    def __repr__(self):
        return '<ScarlettListener>'

    def __init__(self, listener):
        self.con = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(self.con,
                                       'org.scarlett',
                                       Gio.BusNameOwnerFlags.NONE,
                                       None,
                                       None)
        super().__init__(self.con, '/org/scarlett/Listener')

        self.listener = listener
        # self.player.connect('current-changed', self._on_current_changed)
        # self.player.connect('thumbnail-updated', self._on_thumbnail_updated)
        # self.player.connect('playback-status-changed', self._on_playback_status_changed)
        # self.player.connect('repeat-mode-changed', self._on_repeat_mode_changed)
        # self.player.connect('volume-changed', self._on_volume_changed)
        # self.player.connect('prev-next-invalidated', self._on_prev_next_invalidated)
        # self.player.connect('seeked', self._on_seeked)
        # self.player.connect('playlist-changed', self._on_playlist_changed)
        self.dbus_stack = []
        self.pipelines_stack = []
        self.elements_stack = []

        self._message = 'This is the DBusServer'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = True
        self.terminate = False

        self.capsfilter_queue_overrun_handler = None

        # # Thread manager, maximum of 1 since it'll be long running
        # self.manager = FooThreadManager(1)

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

##########################################################################################
# NOTE: I USED CODE SNIPPETS BELOW TO SETUP ^
##########################################################################################
# bus.own_name(name='org.scarlett')
# sl = ScarlettListener(bus=bus.con, path='/org/scarlett/Listener')
# bus = SessionBus()
# ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')  # NOQA
#
# self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
# self.proxy = Gio.DBusProxy.new_sync(self.bus,
#                                     Gio.DBusProxyFlags.NONE,
#                                     None,
#                                     'com.example.service',
#                                     '/com/example/service',
#                                     'com.example.service',
#                                     None)
#
# # NOTE: This is a proxy dbus command
# service = bus.get_object('com.example.service', "/com/example/service")
# self._quit = service.get_dbus_method(
#     'quit', 'com.example.service.Quit')
# self._tasker_connected = service.get_dbus_method(
#     'emitConnectedToListener',
#     'com.example.service.emitConnectedToListener')
    #########################################################
    # Scarlett dbus signals ( out = func args )
    #########################################################

    def KeywordRecognizedSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))
        bus = self.dbus_stack[0]
        logger.debug("Inside KeywordRecognizedSignal. Dump bus object")
        pp.pprint(bus)
        kw_rec_status = GLib.Variant("(ss)", (message, scarlett_sound))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'KeywordRecognizedSignal',
                        kw_rec_status)

    def CommandRecognizedSignal(self, message, scarlett_sound, scarlett_cmd):
        logger.debug(" sending message: {}".format(message))
        bus = self.dbus_stack[0]
        cmd_rec_status = GLib.Variant(
            "(sss)", (message, scarlett_sound, scarlett_cmd))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'CommandRecognizedSignal',
                        cmd_rec_status)

    def SttFailedSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))
        bus = self.dbus_stack[0]
        stt_failed_status = GLib.Variant("(ss)", (message, scarlett_sound))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'SttFailedSignal',
                        stt_failed_status)

    def ListenerCancelSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))
        bus = self.dbus_stack[0]
        listener_cancel_status = GLib.Variant(
            "(ss)", (message, scarlett_sound))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'ListenerCancelSignal',
                        listener_cancel_status)

    def ListenerReadySignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))
        bus = self.dbus_stack[0]
        listener_rdy_status = GLib.Variant("(ss)", (message, scarlett_sound))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'ListenerReadySignal',
                        listener_rdy_status)

    def ConnectedToListener(self, scarlett_plugin):
        logger.debug(" sending message: {}".format(scarlett_plugin))
        bus = self.dbus_stack[0]
        conn_to_lis_status = GLib.Variant("s", scarlett_plugin)
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'ConnectedToListener',
                        conn_to_lis_status)

    #########################################################
    # Scarlett dbus methods in = func args, out = return values
    #########################################################

    def emitKeywordRecognizedSignal(self):
        global SCARLETT_LISTENING
        # you emit signals by calling the signal's skeleton method
        self.KeywordRecognizedSignal(self._status_kw_match, SCARLETT_LISTENING)
        return SCARLETT_LISTENING

    def emitCommandRecognizedSignal(self, command):
        global SCARLETT_RESPONSE
        self.CommandRecognizedSignal(self._status_cmd_match,
                                     SCARLETT_RESPONSE,
                                     command)
        return SCARLETT_RESPONSE

    def emitSttFailedSignal(self):
        global SCARLETT_FAILED
        self.SttFailedSignal(self._status_stt_failed, SCARLETT_FAILED)
        return SCARLETT_FAILED

    def emitListenerCancelSignal(self):
        global SCARLETT_CANCEL
        self.ListenerCancelSignal(self._status_cmd_cancel, SCARLETT_CANCEL)
        return SCARLETT_CANCEL

    def emitListenerReadySignal(self):
        global SCARLETT_LISTENING
        self.ListenerReadySignal(self._status_ready, SCARLETT_LISTENING)
        return SCARLETT_LISTENING

    def emitConnectedToListener(self, scarlett_plugin):
        logger.debug("  sending message")
        self.ConnectedToListener(scarlett_plugin)
        return " {} is connected to ScarlettListener".format(scarlett_plugin)

    def emitListenerMessage(self):
        logger.debug("  sending message")
        return self._message

    def quit(self):
        self.loop.quit()

    #########################################################
    # END Scarlett dbus methods
    #########################################################

    #########################################################
    # START Dbus Introspection method calls required
    #########################################################

    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name)[property_name]

    def GetAll(self, interface_name):
        if interface_name == ScarlettListener.LISTENER_IFACE:
            return {
                'CanQuit': GLib.Variant('b', True),
                'Fullscreen': GLib.Variant('b', False),
                'HasTrackList': GLib.Variant('b', True),
                'Identity': GLib.Variant('s', 'Scarlett'),
                'DesktopEntry': GLib.Variant('s', 'scarlett-listener')
            }
        elif interface_name == 'org.freedesktop.DBus.Properties':
            return {}
        elif interface_name == 'org.freedesktop.DBus.Introspectable':
            return {}
        else:
            raise Exception(
                'org.scarlett.ScarlettListener1',
                'This object does not implement the %s interface'
                % interface_name)

    def Set(self, interface_name, property_name, new_value):
        if interface_name == ScarlettListener.LISTENER_IFACE:
            if property_name == 'Fullscreen':
                pass
        else:
            raise Exception(
                'org.scarlett.ScarlettListener1',
                'This object does not implement the %s interface'
                % interface_name)

    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        self.con.emit_signal(None,
                             '/org/scarlett/Listener',
                             'org.freedesktop.DBus.Properties',
                             'PropertiesChanged',
                             GLib.Variant.new_tuple(GLib.Variant('s', interface_name),
                                                    GLib.Variant('a{sv}', changed_properties),
                                                    GLib.Variant('as', invalidated_properties)))

    def Introspect(self):
        return self.__doc__

    def scarlett_reset_listen(self):
        self.failed = 0
        self.kw_found = 0

    def cancel_listening(self):
        logger.debug("Inside cancel_listening function")
        self.scarlett_reset_listen()
        logger.debug("self.failed = %i" % (self.failed))
        logger.debug(
            "self.keyword_identified = %i" %
            (self.kw_found))

    def get_pocketsphinx_definition(self, device, hmm, lm, dic, override=False):
        """
        GST_DEBUG=2,pocketsphinx*:5 gst-launch-1.0 alsasrc device=plughw:CARD=Device,DEV=0 ! \
                                                    queue name=capsfilter_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    capsfilter caps='audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved' ! \
                                                    audioconvert ! \
                                                    audioresample ! \
                                                    pocketsphinx \
                                                    name=asr \
                                                    lm=~/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm/1473.lm \
                                                    dict=~/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict/1473.dic \
                                                    hmm=~/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us
                                                    bestpath=true ! \
                                                    tee name=tee ! \
                                                    queue name=appsink_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    appsink caps='audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved' \
                                                    drop=false max-buffers=10 sync=false \
                                                    emit-signals=true tee.
                                                    queue name=fakesink_queue \
                                                          leaky=2 \
                                                          max-size-buffers=0 \
                                                          max-size-time=0 \
                                                          max-size-bytes=0 ! \
                                                    fakesink sync=false
        """
        logger.debug("Inside get_pocketsphinx_definition")

        if override:
            _gst_launch = override
        else:
            # ['alsasrc device=' +
            #                device,
            #                'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
            #                'audioconvert',
            #                'audioresample',
            #                'audio/x-raw,format=S16LE,channels=1,layout=interleaved',
            #                'pocketsphinx name=asr bestpath=0',
            #                'queue leaky=2',
            #                'fakesink']
            _gst_launch = ['alsasrc device=' +
                           device,
                           # source: https://github.com/walterbender/story/blob/master/grecord.py
                           # without a buffer here, gstreamer struggles at the start of the
                           # recording and then the A/V sync is bad for the whole video
                           # (possibly a gstreamer/ALSA bug -- even if it gets caught up, it
                           # should be able to resync without problem)
                           'queue name=capsfilter_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           'capsfilter name=capsfilter caps=audio/x-raw,format=S16LE,channels=1,layout=interleaved',
                           'audioconvert name=audioconvert',
                           'audioresample name=audioresample',
                           'identity name=ident',
                           'pocketsphinx name=asr',
                           'tee name=tee',
                           'queue name=appsink_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           #  caps=audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved   # NOQA
                           'appsink name=appsink drop=false max-buffers=10 sync=false emit-signals=true tee.',
                           'queue leaky=2 name=fakesink_queue',
                           'fakesink']

        return _gst_launch

    # SOURCE: player.py in gnome-music for idle_add thread
    # def _update_position_callback(self):
    #     position = self.player.query_position(Gst.Format.TIME)[1] / 1000000000
    #     if position > 0:
    #         self.progressScale.set_value(position * 60)
    #         self.played_seconds += 1
    #         try:
    #             percentage = self.played_seconds / self.duration
    #             if not self.scrobbled and percentage > 0.4:
    #                 current_media = self.get_current_media()
    #                 self.scrobbled = True
    #                 if current_media:
    #                     just_played_url = self.get_current_media().get_url()
    #                     t = Thread(target=self.scrobble_song, args=(just_played_url,))
    #                     t.setDaemon(True)
    #                     t.start()
    #         except Exception as e:
    #             logger.warn("Error: %s, %s", e.__class__, e)
    #     return True

    def run_pipeline(self, device=None, hmm=None, lm=None, dict_ps=None):
        """Holds the PocketSphinx Pipeline we'll use for recognition

    The idea here is that the Gstreamer/PocketSphinx back-end is isolated from
    the GUI code, with the idea that we might be able to add in another backend
    at some point in the future...

    Here's the gst-inspect from the pocketsphinx component:
    Element Properties:
      name                : The name of the object
                            flags: readable, writable
                            String. Default: "pocketsphinx0"
      parent              : The parent of the object
                            flags: readable, writable
                            Object of type "GstObject"
      hmm                 : Directory containing acoustic model parameters
                            flags: readable, writable
                            String. Default: "/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us"
      lm                  : Language model file
                            flags: readable, writable
                            String. Default: "/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us.lm.bin"
      lmctl               : Language model control file (for class LMs)
                            flags: readable, writable
                            String. Default: null
      dict                : Dictionary File
                            flags: readable, writable
                            String. Default: "/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/cmudict-en-us.dict"
      fsg                 : Finite state grammar file
                            flags: readable, writable
                            String. Default: null
      fwdflat             : Enable Flat Lexicon Search
                            flags: readable, writable
                            Boolean. Default: true
      bestpath            : Enable Graph Search
                            flags: readable, writable
                            Boolean. Default: true
      maxhmmpf            : Maximum number of HMMs searched per frame
                            flags: readable, writable
                            Integer. Range: 1 - 100000 Default: 30000
      maxwpf              : Maximum number of words searched per frame
                            flags: readable, writable
                            Integer. Range: 1 - 100000 Default: -1
      beam                : Beam width applied to every frame in Viterbi search
                            flags: readable, writable
                            Double. Range:              -1 -               1 Default:           1e-48
      wbeam               : Beam width applied to phone transitions
                            flags: readable, writable
                            Double. Range:              -1 -               1 Default:           7e-29
      pbeam               : Beam width applied to phone transitions
                            flags: readable, writable
                            Double. Range:              -1 -               1 Default:           1e-48
      dsratio             : Evaluate acoustic model every N frames
                            flags: readable, writable
                            Integer. Range: 1 - 10 Default: 1
      latdir              : Output Directory for Lattices
                            flags: readable, writable
                            String. Default: null
      lmname              : Language model name (to select LMs from lmctl)
                            flags: readable, writable
                            String. Default: null
      decoder             : The underlying decoder
                            flags: readable
                            Boxed pointer of type "PSDecoder"
    """

# DISABLED #        self.queue = queue.Queue(QUEUE_SIZE)

# DISABLED #        # This wil get filled with an exception if opening fails.
# DISABLED #        self.read_exc = None
# DISABLED #        self.dot_exc = None

# DISABLED #        pipeline = Gst.parse_launch(' ! '.join(
# DISABLED #                                    self.get_pocketsphinx_definition(device,
# DISABLED #                                                                     hmm,
# DISABLED #                                                                     lm,
# DISABLED #                                                                     dict_ps)))

        self.init_gst(device, hmm, lm, dict_ps)

        # # Add pipeline obj to stack we can pull from later
        # self.pipelines_stack.append(pipeline)
        #
        # # get gst pipeline element pocketsphinx and set properties
        # pocketsphinx = pipeline.get_by_name('asr')
        # if hmm:
        #     pocketsphinx.set_property('hmm', hmm)
        # if lm:
        #     pocketsphinx.set_property('lm', lm)
        # if dict_ps:
        #     pocketsphinx.set_property('dict', dict_ps)
        #
        # pocketsphinx.set_property('fwdflat', True)  # Enable Flat Lexicon Search | Default: true
        # pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        # pocketsphinx.set_property('dsratio', 1)  # Evaluate acoustic model every N frames |  Integer. Range: 1 - 10 Default: 1
        # pocketsphinx.set_property('maxhmmpf', 3000)  # Maximum number of HMMs searched per frame | Integer. Range: 1 - 100000 Default: 30000
        # pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        # # pocketsphinx.set_property('maxwpf', -1)  # pocketsphinx.set_property('maxwpf', 20)  # Maximum number of words searched per frame | Range: 1 - 100000 Default: -1
        #
        # gst_bus = pipeline.get_bus()
        #
        # # Start playing
        # ret = pipeline.set_state(Gst.State.PLAYING)
        #
        # if ret == Gst.StateChangeReturn.FAILURE:
        #     logger.error("ERROR: Unable to set the pipeline to the playing state")
        #
        # self.emitListenerReadySignal()
        #
        # print "ScarlettListener running..."
        # if self.create_dot:
        #     self.on_debug_activate()
        #
        # # wait until error or EOS
        # while True:
        #     try:
        #         msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
        #         if msg:
        #             # if msg.get_structure():
        #             #    print(msg.get_structure().to_string())
        #
        #             logger.debug("msg.type: {}".format(msg.type))
        #
        #             if msg.type == Gst.MessageType.EOS:
        #                 break
        #             struct = msg.get_structure()
        #             if struct and struct.get_name() == 'pocketsphinx':
        #                 if struct['final']:
        #                     logger.info(struct['hypothesis'])
        #                     if self.kw_found == 1:
        #                         # If keyword is set AND qualifier
        #                         # then perform action
        #                         self.run_cmd(struct['hypothesis'])
        #                     else:
        #                         # If it's the main keyword,
        #                         # set values wait for qualifier
        #                         self.result(struct['hypothesis'])
        #     except KeyboardInterrupt:
        #         self.terminate = True
        #         pipeline.send_event(Gst.Event.new_eos())
        #         self.close(True)
        #
        #     # Taken from basic-tutorial-7.py in python-gst-tutorial
        #     if self.terminate:
        #         break
        #
        # # Free resources
        # # pipeline.set_state(Gst.State.NULL)
        # logger.info("ScarlettListener stopped")

    # NOTE: This function generates the dot file, checks that graphviz in installed and
    # then finally generates a png file, which it then displays
    def on_debug_activate(self):
        dotfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-listener.dot"
        pngfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-listener-pipeline.png"  # NOQA
        if os.access(dotfile, os.F_OK):
            os.remove(dotfile)
        if os.access(pngfile, os.F_OK):
            os.remove(pngfile)
        Gst.debug_bin_to_dot_file(self.pipelines_stack[0],
                                  Gst.DebugGraphDetails.ALL, "generator-listener")
        os.system('/usr/bin/dot' + " -Tpng -o " + pngfile + " " + dotfile)

    def result(self, final_hyp):
        """Forward result signals on the bus to the main thread."""
        logger.debug("Inside result function")
        logger.debug("final_hyp: {}".format(final_hyp))
        pp.pprint(final_hyp)
        logger.debug("kw_to_find: {}".format(self.kw_to_find))
        if final_hyp in self.kw_to_find:
            logger.debug(
                "HYP-IS-SOMETHING: " +
                final_hyp +
                "\n\n\n")
            self.failed = 0
            self.kw_found = 1
            self.emitKeywordRecognizedSignal()
        else:
            failed_temp = self.failed + 1
            self.failed = failed_temp
            logger.debug(
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.emitSttFailedSignal()
                self.scarlett_reset_listen()

    def run_cmd(self, final_hyp):
        logger.debug("Inside run_cmd function")
        logger.debug("KEYWORD IDENTIFIED BABY")
        logger.debug(
            "self.kw_found = %i" %
            (self.kw_found))
        if final_hyp == 'CANCEL':
            self.emitListenerCancelSignal()
            self.cancel_listening()
        else:
            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified
            self.emitCommandRecognizedSignal(final_hyp)
            logger.info(
                " Command = {}".format(final_hyp))
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def init_gst(self, device=None, hmm=None, lm=None, dict_ps=None):
        logger.debug("Inside init_gst")
        self.running = False
        self.finished = False
        self.ready_sem = threading.Semaphore(0)

        self.queue = queue.Queue(QUEUE_SIZE)

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        pipeline = Gst.parse_launch(' ! '.join(
                                    self.get_pocketsphinx_definition(device,
                                                                     hmm,
                                                                     lm,
                                                                     dict_ps)))
        logger.debug("After get_pocketsphinx_definition")
        # Add pipeline obj to stack we can pull from later
        self.pipelines_stack.append(pipeline)

        gst_bus = pipeline.get_bus()
        # gst_bus = pipeline.get_gst_bus()
        gst_bus.add_signal_watch()

        self.bus_message_handler_id = self.bus.connect("message", self.on_message)

        gst_bus.connect("message::eos", self._on_message)
        gst_bus.connect("message::error", self._on_message)
        gst_bus.connect("message::state-changed", self._on_state_changed)

        appsink = pipeline.get_by_name('appsink')
        appsink.set_property(
            'caps',
            Gst.Caps.from_string('audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved'),
        )
        # TODO set endianness?
        # Set up the characteristics of the output. We don't want to
        # drop any data (nothing is real-time here); we should bound
        # the memory usage of the internal queue; and, most
        # importantly, setting "sync" to False disables the default
        # behavior in which you consume buffers in real time. This way,
        # we get data as soon as it's decoded.
        appsink.set_property('drop', False)
        appsink.set_property('max-buffers', BUFFER_SIZE)
        appsink.set_property('sync', False)

        # The callback to receive decoded data.
        appsink.set_property('emit-signals', True)
        appsink.connect("new-sample", self._new_sample)

        self.caps_handler = appsink.get_static_pad("sink").connect(
            "notify::caps", self._notify_caps
        )

        self.elements_stack.append(appsink)

        # get gst pipeline element pocketsphinx and set properties
        pocketsphinx = pipeline.get_by_name('asr')
        if hmm:
            pocketsphinx.set_property('hmm', hmm)
        if lm:
            pocketsphinx.set_property('lm', lm)
        if dict_ps:
            pocketsphinx.set_property('dict', dict_ps)

        pocketsphinx.set_property('fwdflat', True)  # Enable Flat Lexicon Search | Default: true
        pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        pocketsphinx.set_property('dsratio', 1)  # Evaluate acoustic model every N frames |  Integer. Range: 1 - 10 Default: 1
        pocketsphinx.set_property('maxhmmpf', 3000)  # Maximum number of HMMs searched per frame | Integer. Range: 1 - 100000 Default: 30000
        pocketsphinx.set_property('bestpath', True)  # Enable Graph Search | Boolean. Default: true
        # pocketsphinx.set_property('maxwpf', -1)  # pocketsphinx.set_property('maxwpf', 20)  # Maximum number of words searched per frame | Range: 1 - 100000 Default: -1

        self.elements_stack.append(pocketsphinx)

        capsfilter_queue = pipeline.get_by_name('capsfilter_queue')
        capsfilter_queue.set_property('leaky', True)  # prefer fresh data
        # capsfilter_queue.set_property('max-size-time', 5000000000)  # 5 seconds
        # capsfilter_queue.set_property('max-size-buffers', 500)
        # capsfilter_queue.set_property('max-size-bytes', 0)
        capsfilter_queue.set_property('silent', False)
        capsfilter_queue.set_property('max-size-time', 0)  # 0 seconds
        capsfilter_queue.set_property('max-size-buffers', 0)
        capsfilter_queue.set_property('max-size-bytes', 0)
        self.capsfilter_queue_overrun_handler = capsfilter_queue.connect('overrun', self._log_queue_overrun)

        # capsfilter_queue.connect('overrun', self._on_overrun)
        # capsfilter_queue.connect('underrun', self._on_underrun)
        # capsfilter_queue.connect('pushing', self._on_pushing)
        # capsfilter_queue.connect('running', self._on_running)

        self.elements_stack.append(capsfilter_queue)

        ident = pipeline.get_by_name('ident')
        # ident.connect('handoff', self._on_handoff)

        self.elements_stack.append(ident)

        # 'queue name=capsfilter_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
        # 'capsfilter name=capsfilter caps=audio/x-raw,format=S16LE,channels=1,layout=interleaved',
        # 'audioconvert name=audioconvert',
        # 'audioresample name=audioresample',
        # 'pocketsphinx name=asr',
        # 'tee name=tee',
        # 'queue name=appsink_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
        # #  caps=audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved   # NOQA
        # 'appsink name=appsink drop=false max-buffers=10 sync=false emit-signals=true tee.',
        # 'queue leaky=2 name=fakesink_queue',

        logger.debug("After all self.elements_stack.append() calls")
        # Set up the queue for data and run the main thread.
        self.queue = queue.Queue(QUEUE_SIZE)
        self.thread = get_loop_thread()

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        # Return as soon as the stream is ready!
        self.running = True
        self.got_caps = False
        ret = pipeline.set_state(Gst.State.PLAYING)
        logger.debug("pipeline.set_state(Gst.State.PLAYING)")
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("ERROR: Unable to set the pipeline to the playing state")
        self.on_debug_activate()
        logger.debug("BEFORE: self.ready_sem.acquire()")
        self.ready_sem.acquire()
        logger.debug("AFTER: self.ready_sem.acquire()")
        logger.info("Press Ctrl+C to quit ...")

        if self.read_exc:
            # An error occurred before the stream became ready.
            self.close(True)
            raise self.read_exc

    def _on_handoff(self, element, buf):
        logger.debug('buf:')
        pp.pprint(buf)
        pp.pprint(dir(buf))
        logger.debug('on_handoff - %d bytes' % len(buf))
        # print 'buf =', buf
        # print 'dir(buf) =', dir(buf)

        if self.signed is None:
            # only ever one caps struct on our buffers
            struct = buf.get_caps().get_structure(0)

            # I think these are always set too, but catch just in case
            try:
                self.signed = struct["signed"]
                self.depth = struct["depth"]
                self.rate = struct["rate"]
                self.channels = struct["channels"]
            except:
                logger.debug('on_handoff: missing caps')
                pass

        # raw = str(buf)
        #
        # # print 'len(raw) =', len(raw)
        #
        # sm = 0
        # for i in range(0, len(raw)):
        #     sm += ord(raw[i])
        # # print sm
        # FIXEME: Add somthing like analyse.py
        # SOURCE: https://github.com/jcupitt/huebert/blob/master/huebert/audio.py

    def _on_state_changed(self, bus, msg):
        states = msg.parse_state_changed()
        # To state is PLAYING
        if msg.src.get_name() == "pipeline0" and states[1] == 4:
            logger.info('Inside pipeline0 on _on_state_changed')
            logger.info("State: {}".format(states[1]))
            self.ready_sem.release()
            return False
        else:
            logger.error('NOTHING RETURNED in _on_state_changed')
            logger.info("State: {}".format(states[1]))

    def _on_overrun(self, element):
        logging.debug('on_overrun')

    def _on_underrun(self, element):
        logging.debug('on_underrun')

    def _on_running(self, element):
        logging.debug('on_running')

    def _on_pushing(self, element):
        logging.debug('on_pushing')

    def _notify_caps(self, pad, args):
        """The callback for the sinkpad's "notify::caps" signal.
        """
        # The sink has started to receive data, so the stream is ready.
        # This also is our opportunity to read information about the
        # stream.
        self.got_caps = True

        # Allow constructor to complete.
        self.ready_sem.release()

    _got_a_pad = False

    def _log_queue_overrun(self, queue):
        cbuffers = queue.get_property('current-level-buffers')
        cbytes = queue.get_property('current-level-bytes')
        ctime = queue.get_property('current-level-time')

    def _new_sample(self, sink):
        """The callback for appsink's "new-sample" signal.
        """
        if self.running:
            # New data is available from the pipeline! Dump it into our
            # queue (or possibly block if we're full).
            buf = sink.emit('pull-sample').get_buffer()
            self.queue.put(buf.extract_dup(0, buf.get_size()))
        return Gst.FlowReturn.OK

    def _on_message(self, bus, message):
        """The callback for GstBus's "message" signal (for two kinds of
        messages).
        """
        if not self.finished:
            struct = message.get_structure()

            if message.type == Gst.MessageType.EOS:
                # The file is done. Tell the consumer thread.
                self.queue.put(SENTINEL)
                if not self.got_caps:
                    logger.error(
                        "If the stream ends before _notify_caps was called, this is an invalid stream.")
                    # If the stream ends before _notify_caps was called, this
                    # is an invalid file.
                    self.read_exc = generator_utils.NoStreamError()
                    self.ready_sem.release()
            elif struct and struct.get_name() == 'pocketsphinx':
                        if struct['final']:
                            logger.info(struct['hypothesis'])
                            if self.kw_found == 1:
                                # If keyword is set AND qualifier
                                # then perform action
                                self.run_cmd(struct['hypothesis'])
                            else:
                                # If it's the main keyword,
                                # set values wait for qualifier
                                self.result(struct['hypothesis'])
            elif message.type == Gst.MessageType.ERROR:
                gerror, debug = message.parse_error()
                if 'not-linked' in debug:
                    logger.error('not-linked')
                    self.read_exc = generator_utils.NoStreamError()
                else:
                    logger.info("FileReadError")
                    self.read_exc = generator_utils.FileReadError(debug)
                self.ready_sem.release()

    # Iteration.

    def next(self):
        # Wait for data from the Gstreamer callbacks.
        val = self.queue.get()
        if val == SENTINEL:
            # End of stream.
            raise StopIteration
        return val

    # For Python 3 compatibility.
    __next__ = next

    def __iter__(self):
        return self

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True

            # Unregister for signals, which we registered for above with
            # `add_signal_watch`. (Without this, GStreamer leaks file
            # descriptors.)
            # self.pipeline.get_bus().remove_signal_watch()
            logger.debug('BEFORE p = self.pipelines_stack[0]')
            p = self.pipelines_stack[0]
            p.get_bus().remove_signal_watch()
            logger.debug('AFTER p.get_bus().remove_signal_watch()')

            # Block spurious signals.
            appsink = self.elements_stack[0]
            appsink.get_static_pad("sink").disconnect(self.caps_handler)

            # Make space in the output queue to let the decoder thread
            # finish. (Otherwise, the thread blocks on its enqueue and
            # the interpreter hangs.)
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass

            # Halt the pipeline (closing file).
            p.set_state(Gst.State.NULL)

            # Delete the pipeline object. This seems to be necessary on Python
            # 2, but not Python 3 for some reason: on 3.5, at least, the
            # pipeline gets dereferenced automatically.
            del p

        # if self.terminate or force:
        #     self.finished = True
        #
        #     p = self.pipelines_stack[0]
        #     p.get_bus().remove_signal_watch()
        #     p.set_state(Gst.State.NULL)
        #
        #     # Unregister for signals, which we registered for above with
        #     # `add_signal_watch`. (Without this, GStreamer leaks file
        #     # descriptors.)
        #     # self.pipeline.get_bus().remove_signal_watch()
        #
        #     # # Stop reading the file.
        #     # self.source.set_property("uri", None)
        #     # # Block spurious signals.
        #     # self.appsink.get_static_pad("sink").disconnect(self.caps_handler)
        #
        #     # Make space in the output queue to let the decoder thread
        #     # finish. (Otherwise, the thread blocks on its enqueue and
        #     # the interpreter hangs.)
        #     try:
        #         self.queue.get_nowait()
        #     except queue.Empty:
        #         pass
        #
        #     # # Halt the pipeline (closing file).
        #     # self.pipeline.set_state(Gst.State.NULL)
        #
        #     # Delete the pipeline object. This seems to be necessary on Python
        #     # 2, but not Python 3 for some reason: on 3.5, at least, the
        #     # pipeline gets dereferenced automatically.
        #     del p

    def __del__(self):
        self.close()

    # Context manager.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

if __name__ == '__main__':
    from pydbus import SessionBus
    bus = SessionBus()
    bus.own_name(name='org.scarlett')
    sl = ScarlettListener(bus=bus.con, path='/org/scarlett/Listener')

    LANGUAGE_VERSION = 1473
    HOMEDIR = "/home/pi"
    LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm".format(
        HOMEDIR)
    DICT_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict".format(
        HOMEDIR)
    LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
    DICT_PATH = "{}/{}.dic".format(DICT_FILE_HOME, LANGUAGE_VERSION)
    HMM_PATH = "{}/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us".format(
        HOMEDIR)
    bestpath = 0
    PS_DEVICE = 'plughw:CARD=Device,DEV=0'

    parser = argparse.ArgumentParser(description='Recognize speech from audio')
    parser.add_argument('--device',
                        default=PS_DEVICE,
                        help='Pocketsphinx audio source device')
    parser.add_argument('--hmm',
                        default=HMM_PATH,
                        help='Path to a pocketsphinx HMM data directory')
    parser.add_argument('--lm',
                        default=LM_PATH,
                        help='Path to a pocketsphinx language model file')
    parser.add_argument('--dict_ps',
                        default=DICT_PATH,
                        help='Path to a pocketsphinx CMU dictionary file')
    args = parser.parse_args()

# TEMP #    def sigint_handler(*args):
# TEMP #        """Exit on Ctrl+C"""
# TEMP #        # Unregister handler, next Ctrl-C will kill app
# TEMP #        # TODO: figure out if this is really needed or not
# TEMP #        signal.signal(signal.SIGINT, signal.SIG_DFL)
# TEMP #
# TEMP #        sl.close(True)
# TEMP #
# TEMP #    signal.signal(signal.SIGINT, sigint_handler)
# TEMP #
# TEMP #    # with generator_utils.time_logger('Espeak Subprocess To File'):
# TEMP #    #     sl.run_pipeline(**vars(args))
# TEMP #
# TEMP #    sl.run_pipeline(**vars(args))

    def sigint_handler(*args):
        """Exit on Ctrl+C"""

        # Unregister handler, next Ctrl-C will kill app
        # TODO: figure out if this is really needed or not
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        sl.quit()

    signal.signal(signal.SIGINT, sigint_handler)

    sl.run_pipeline(**vars(args))

    # with generator_utils.time_logger('Scarlett Listener'):
    #     sl.run_pipeline(**vars(args))

    #
    # tts_list = [
    #     'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    # for scarlett_text in tts_list:
    #     with generator_utils.time_logger('Scarlett Speaks'):
    #         ScarlettListener()
