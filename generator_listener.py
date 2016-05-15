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

gst = Gst
HERE = os.path.dirname(__file__)


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
        # self.loop = GLib.MainLoop()
        self.loop = glib_get_loop_thread()
        self.dbus_stack = []
        self.pipelines_stack = []

        self._message = 'This is the DBusServer'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = True
        self.terminate = False

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


class ScarlettListener(Server):  # NOQA
    '''
<node>
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
        print "  sending message"
        self.ConnectedToListener(scarlett_plugin)
        return " {} is connected to ScarlettListener".format(scarlett_plugin)

    def emitListenerMessage(self):
        print "  sending message"
        return self._message

    def quit(self):
        self.loop.quit()

    #########################################################
    # END Scarlett dbus methods
    #########################################################

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
                           'queue name=capsfilter_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           'capsfilter name=capsfilter caps=audio/x-raw,format=S16LE,channels=1,layout=interleaved',
                           'audioconvert name=audioconvert',
                           'audioresample name=audioresample',
                           'pocketsphinx name=asr',
                           'tee name=tee',
                           'queue name=appsink_queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                           #  caps=audio/x-raw,format=(string)S16LE,rate=(int)16000,channels=(int)1,layout=(string)interleaved   # NOQA
                           'appsink name=appsink drop=false max-buffers=10 sync=false emit-signals=true tee.',
                           'queue leaky=2 name=fakesink_queue',
                           'fakesink']

        return _gst_launch

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

    def init_gst(self):
        pass

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

        self.queue = queue.Queue(QUEUE_SIZE)

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        pipeline = Gst.parse_launch(' ! '.join(
                                    self.get_pocketsphinx_definition(device,
                                                                     hmm,
                                                                     lm,
                                                                     dict_ps)))
        # Add pipeline obj to stack we can pull from later
        self.pipelines_stack.append(pipeline)

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

        gst_bus = pipeline.get_bus()

        # Start playing
        ret = pipeline.set_state(Gst.State.PLAYING)

        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("ERROR: Unable to set the pipeline to the playing state")

        self.emitListenerReadySignal()

        print "ScarlettListener running..."
        if self.create_dot:
            self.on_debug_activate()

        # wait until error or EOS
        while True:
            try:
                msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
                if msg:
                    # if msg.get_structure():
                    #    print(msg.get_structure().to_string())

                    logger.debug("msg.type: {}".format(msg.type))

                    if msg.type == Gst.MessageType.EOS:
                        break
                    struct = msg.get_structure()
                    if struct and struct.get_name() == 'pocketsphinx':
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
            except KeyboardInterrupt:
                self.terminate = True
                pipeline.send_event(Gst.Event.new_eos())
                self.close(True)

            # Taken from basic-tutorial-7.py in python-gst-tutorial
            if self.terminate:
                break

        # Free resources
        # pipeline.set_state(Gst.State.NULL)
        logger.info("ScarlettListener stopped")


# def quit(self):
# p = self.pipelines_stack[0]
# p.set_state(Gst.State.NULL)
# self.loop.quit()

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.terminate or force:
            self.finished = True

            p = self.pipelines_stack[0]
            p.get_bus().remove_signal_watch()
            p.set_state(Gst.State.NULL)

            # Unregister for signals, which we registered for above with
            # `add_signal_watch`. (Without this, GStreamer leaks file
            # descriptors.)
            # self.pipeline.get_bus().remove_signal_watch()

            # # Stop reading the file.
            # self.source.set_property("uri", None)
            # # Block spurious signals.
            # self.appsink.get_static_pad("sink").disconnect(self.caps_handler)

            # Make space in the output queue to let the decoder thread
            # finish. (Otherwise, the thread blocks on its enqueue and
            # the interpreter hangs.)
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass

            # # Halt the pipeline (closing file).
            # self.pipeline.set_state(Gst.State.NULL)

            # Delete the pipeline object. This seems to be necessary on Python
            # 2, but not Python 3 for some reason: on 3.5, at least, the
            # pipeline gets dereferenced automatically.
            del p

    def __del__(self):
        self.close()

    # # Context manager.
    # def __enter__(self):
    #     return self

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

    def sigint_handler(*args):
        """Exit on Ctrl+C"""
        # Unregister handler, next Ctrl-C will kill app
        # TODO: figure out if this is really needed or not
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        sl.close(True)

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
