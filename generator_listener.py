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
from gi.repository import GObject, Gst, GLib, Gio  # NOQA
import threading

GObject.threads_init()
Gst.init(None)

Gst.debug_set_active(True)
# NORMALLY WE WANT FIXME LEVEL # Gst.debug_set_default_threshold(3)
Gst.debug_set_default_threshold(1)


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
import time
import random


from IPython.core.debugger import Tracer  # NOQA
from IPython.core import ultratb
import traceback

from gettext import gettext as _

import generator_utils
from generator_utils import trace, abort_on_exception, _IdleObject
# import generator_subprocess
# import generator_player

import scarlett_config

import logging
logger = logging.getLogger('scarlettlogger')
from pydbus import SessionBus
from pydbus.green import sleep

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

SCARLETT_CANCEL = "pi-cancel"
SCARLETT_LISTENING = "pi-listening"
SCARLETT_RESPONSE = "pi-response"
SCARLETT_FAILED = "pi-response2"

# NOTE: GObject.object.connect(detailed_signal: str, handler: function, *args) → handler_id: int

SCARLETT_LISTENER_I_SIGNALS = {
    "completed": (
        GObject.SignalFlags.RUN_LAST, None, []),
    "progress": (
        GObject.SignalFlags.RUN_LAST, None, []),  # percent complete
    "eos": (GObject.SignalFlags.RUN_LAST, None, ()),
    "error": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_STRING, GObject.TYPE_STRING)),
    "died": (GObject.SignalFlags.RUN_LAST, None, ()),
    "async-done": (GObject.SignalFlags.RUN_LAST, None, ()),
    "state-change": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_INT)),
    'playing-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    'playback-status-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
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

loop = GObject.MainLoop()

# Pocketsphinx defaults
LANGUAGE_VERSION = 1473
HOMEDIR = "/home/pi"
LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm".format(HOMEDIR)
DICT_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict".format(HOMEDIR)
LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
DICT_PATH = "{}/{}.dic".format(DICT_FILE_HOME, LANGUAGE_VERSION)
HMM_PATH = "{}/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us".format(HOMEDIR)
bestpath = 0
PS_DEVICE = 'plughw:CARD=Device,DEV=0'


#################################################################
# Managing the Gobject main loop thread.
#################################################################

_shared_loop_thread = None
_loop_thread_lock = threading.RLock()
_listener_thread_lock = threading.RLock()


@abort_on_exception
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
    def make_thread(self, completedCb, progressCb, *args):
        """
        Makes a thread with args. The thread will be started when there is
        a free slot
        """
        running = len(self.fooThreads) - len(self.pendingFooThreadArgs)

        if args not in self.fooThreads:
            thread = ScarlettListenerI(*args)
            # signals run in the order connected. Connect the user completed
            # callback first incase they wish to do something
            # before we delete the thread
            thread.connect("completed", completedCb)
            thread.connect("completed", self._register_thread_completed, *args)
            thread.connect("progress", progressCb)
            # This is why we use args, not kwargs, because args are hashable
            self.fooThreads[args] = thread

            if running < self.maxConcurrentThreads:
                print "Starting %s" % thread
                self.fooThreads[args].start()
            else:
                print "Queuing %s" % thread
                self.pendingFooThreadArgs.append(args)

    # @trace
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


class ScarlettListenerI(threading.Thread, _IdleObject):
    """
    Attempt to take out all Gstreamer logic and put it in a class ouside the dbus server.
    Cancellable thread which uses gobject signals to return information
    to the GUI.
    """
    __gsignals__ = SCARLETT_LISTENER_I_SIGNALS

    device = PS_DEVICE
    hmm = HMM_PATH
    lm = LM_PATH
    dic = DICT_PATH

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

    def __init__(self, *args):
        threading.Thread.__init__(self)
        _IdleObject.__init__(self)

        # Gst.init(None)

        self.running = False
        self.finished = False
        self.ready_sem = threading.Semaphore(0)
        self.queue = queue.Queue(QUEUE_SIZE)

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        self.cancelled = False
        self.name = args[0]
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

    def cancel_listening(self, *args, **kwargs):
        logger.debug("Inside cancel_listening function")
        self.scarlett_reset_listen()
        logger.debug("self.failed = %i" % (self.failed))
        logger.debug(
            "self.keyword_identified = %i" %
            (self.kw_found))

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

    # @trace
    def stop(self):
        p = self.pipelines_stack[0]
        self.state = "stopped"
        self.running = False
        # GST_STATE_NULL is the default state of an element.
        # In this state, it has not allocated any runtime resources,
        # it has not loaded any runtime libraries and it can obviously not handle data.
        p.set_state(Gst.State.NULL)

    def get_pocketsphinx_definition(self, override=False):
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
                           ScarlettListenerI.device,
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

    # @trace
    def cancel(self):
        """
        Threads in python are not cancellable, so we implement our own
        cancellation logic
        """
        self.cancelled = True

    @abort_on_exception
    def run(self, event=None):
        # TODO: WE NEED TO USE A THREADING EVENT OR A RLOCK HERE TO WAIT TILL DBUS SERVICE IS RUNNING TO CONNECT
        # TODO: SIGNALS TO THE DBUS PROXY METHODS WE WANT TO USE
        # TODO: lock.acquire() / event / condition
        # TODO: self.connect_to_dbus()
        # TODO: self.setup_dbus_callbacks_handlers()
        self._connect_to_dbus()
        self.init_gst()
        print "Running %s" % str(self)
        self.play()
        self.emit('playback-status-changed')
        self.emit('playing-changed')
        # FIXME: is this needed? # self.mainloop.run()

    def _connect_to_dbus(self):
        self.bus = SessionBus()
        self.dbus_proxy = self.bus.get("org.scarlett", object_path='/org/scarlett/Listener')  # NOQA
        self.dbus_proxy.emitConnectedToListener('ScarlettListener')
        sleep(2)
        logger.info('_connect_to_dbus')
        ss_cancel_signal = self.bus.subscribe(sender=None,
                                         iface="org.scarlett.Listener",
                                         signal="ListenerCancelSignal",
                                         object="/org/scarlett/Listener",
                                         arg0=None,
                                         flags=0,
                                         signal_fired=self.cancel_listening)

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
        if final_hyp in self.kw_to_find and final_hyp != '':
            logger.debug(
                "HYP-IS-SOMETHING: " +
                final_hyp +
                "\n\n\n")
            self.failed = 0
            self.kw_found = 1
            self.dbus_proxy.emitKeywordRecognizedSignal()  # CHANGEME
        else:
            failed_temp = self.failed + 1
            self.failed = failed_temp
            logger.debug(
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.dbus_proxy.emitSttFailedSignal()  # CHANGEME
                self.scarlett_reset_listen()

    def run_cmd(self, final_hyp):
        logger.debug("Inside run_cmd function")
        logger.debug("KEYWORD IDENTIFIED BABY")
        logger.debug(
            "self.kw_found = %i" %
            (self.kw_found))
        if final_hyp == 'CANCEL':
            self.dbus_proxy.emitListenerCancelSignal()  # CHANGEME
            self.cancel_listening()
        else:
            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified
            self.dbus_proxy.emitCommandRecognizedSignal(final_hyp)  # CHANGEME
            logger.info(
                " Command = {}".format(final_hyp))
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def init_gst(self):
        logger.debug("Inside init_gst")
        self.start_time = time.time()
        pipeline = Gst.parse_launch(' ! '.join(self.get_pocketsphinx_definition()))
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
        self.gst_bus_stack.append(gst_bus)

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
        if ScarlettListenerI.hmm:
            pocketsphinx.set_property('hmm', ScarlettListenerI.hmm)
        if ScarlettListenerI.lm:
            pocketsphinx.set_property('lm', ScarlettListenerI.lm)
        if ScarlettListenerI.dic:
            pocketsphinx.set_property('dict', ScarlettListenerI.dic)

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
            # logger.error('NOTHING RETURNED in _on_state_changed')
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
                pp.pprint(("gerror,debug:", gerror, debug))
                if 'not-linked' in debug:
                    logger.error('not-linked')
                    self.read_exc = generator_utils.NoStreamError()
                elif 'No such device' in debug:
                    logger.error('No such device')
                    self.read_exc = generator_utils.NoStreamError()
                else:
                    logger.info("FileReadError")
                    pp.pprint(("SOME FileReadError", bus, message, struct, struct.get_name()))
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

    def __del__(self):
        self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class Demo:
    """Demo Class strictly for testing out ScarlettListenerI."""

    @abort_on_exception
    def __init__(self):
        self.manager = FooThreadManager(1)
        self.add_thread()

    # @trace
    def quit(self):
        # NOTE: when we connect this as a callback to a signal being emitted, we'll need to chage quit to look
        # like this quit(self, sender, event):
        self.manager.stop_all_threads(block=True)

    # @trace
    def stop_threads(self, *args):
        self.manager.stop_all_threads()

    # @trace
    def add_thread(self):
        # NOTE: if we do this via a gobject connect we need def add_thread(self, sender):
        # make a thread and start it
        name = "Thread #%s" % random.randint(0, 1000)
        self.manager.make_thread(
            self.thread_finished,  # completedCb
            self.thread_progress,  # progressCb
            name)  # args[1]

    # @trace
    def thread_finished(self, thread):
        logger.debug("thread_finished.")

    # @trace
    def thread_progress(self, thread):
        logger.debug("thread_progress.")

if __name__ == '__main__':
    # from pydbus import SessionBus
    # bus = SessionBus()
    # bus.own_name(name='org.scarlett')
    # sl = ScarlettListener(bus=bus.con, path='/org/scarlett/Listener')
    # # bus.publish("org.scarlett.Listener", sl)
    # loop.run()
    #
    # def sigint_handler(*args):
    #     """Exit on Ctrl+C"""
    #
    #     # Unregister handler, next Ctrl-C will kill app
    #     # TODO: figure out if this is really needed or not
    #     signal.signal(signal.SIGINT, signal.SIG_DFL)
    #
    #     sl.Quit()
    #
    # signal.signal(signal.SIGINT, sigint_handler)

    demo = Demo()
    loop.run()

    def sigint_handler(*args):
        """Exit on Ctrl+C"""

        # Unregister handler, next Ctrl-C will kill app
        # TODO: figure out if this is really needed or not
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        demo.quit()

        loop.quit()

    signal.signal(signal.SIGINT, sigint_handler)
