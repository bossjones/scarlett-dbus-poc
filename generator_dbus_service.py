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

# try:
#     import queue
# except ImportError:
#     import Queue as queue

# try:
#     from urllib.parse import quote
# except ImportError:
#     from urllib import quote


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
from generator_utils import trace, abort_on_exception
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
loop = GObject.MainLoop()

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

    def __init__(self):
        GObject.GObject.__init__(self)

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


class Server(object):

    def __repr__(self):
        return '<Server>'

    def __init__(self, bus, path):
        super(Server, self).__init__()
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


class ScarlettListener(_IdleObject, Server):  # NOQA
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

    def __repr__(self):
        return '<ScarlettListener>'

    @abort_on_exception
    def __init__(self, bus, path):
        _IdleObject.__init__(self)

        self.con = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        Gio.bus_own_name_on_connection(self.con,
                                       'org.scarlett',
                                       Gio.BusNameOwnerFlags.NONE,
                                       None,
                                       None)
        Server.__init__(self, bus, path)
        #super(ScarlettListener, self).__init__(self.con, '/org/scarlett/Listener')
        super(ScarlettListener, self).__init__()

        # self.listener = listener
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

if __name__ == '__main__':
    from pydbus import SessionBus
    bus = SessionBus()
    bus.own_name(name='org.scarlett')
    sl = ScarlettListener(bus=bus.con, path='/org/scarlett/Listener')

    # LANGUAGE_VERSION = 1473
    # HOMEDIR = "/home/pi"
    # LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm".format(
    #     HOMEDIR)
    # DICT_FILE_HOME = "{}/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict".format(
    #     HOMEDIR)
    # LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
    # DICT_PATH = "{}/{}.dic".format(DICT_FILE_HOME, LANGUAGE_VERSION)
    # HMM_PATH = "{}/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us".format(
    #     HOMEDIR)
    # bestpath = 0
    # PS_DEVICE = 'plughw:CARD=Device,DEV=0'
    #
    # parser = argparse.ArgumentParser(description='Recognize speech from audio')
    # parser.add_argument('--device',
    #                     default=PS_DEVICE,
    #                     help='Pocketsphinx audio source device')
    # parser.add_argument('--hmm',
    #                     default=HMM_PATH,
    #                     help='Path to a pocketsphinx HMM data directory')
    # parser.add_argument('--lm',
    #                     default=LM_PATH,
    #                     help='Path to a pocketsphinx language model file')
    # parser.add_argument('--dict_ps',
    #                     default=DICT_PATH,
    #                     help='Path to a pocketsphinx CMU dictionary file')
    # args = parser.parse_args()

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

    loop.run()

    # sl.run_pipeline(**vars(args))

    # with generator_utils.time_logger('Scarlett Listener'):
    #     sl.run_pipeline(**vars(args))

    #
    # tts_list = [
    #     'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    # for scarlett_text in tts_list:
    #     with generator_utils.time_logger('Scarlett Speaks'):
    #         ScarlettListener()
