#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys

SCARLETT_DEBUG = 1

if SCARLETT_DEBUG:
    # Setting GST_DEBUG_DUMP_DOT_DIR environment variable enables us to have a
    # dotfile generated
    os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug"
    os.putenv('GST_DEBUG_DUMP_DIR_DIR', '/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug')


import argparse
import pprint
pp = pprint.PrettyPrinter(indent=4)

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from dbus.mainloop.glib import threads_init

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

import scarlett_config

SCARLETT_CANCEL = "pi-cancel"
SCARLETT_LISTENING = "pi-listening"
SCARLETT_RESPONSE = "pi-response"
SCARLETT_FAILED = "pi-response2"

from gettext import gettext as _

gst = Gst


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


class ScarlettListener(dbus.service.Object):
    LISTENER_IFACE = 'com.example.service'
    LISTENER_PLAYER_IFACE = 'com.example.service.Player'
    LISTENER_TRACKLIST_IFACE = 'com.example.service.TrackList'
    LISTENER_PLAYLISTS_IFACE = 'com.example.service.Playlists'
    LISTENER_EVENTS_IFACE = 'com.example.service.event'

    # def __repr__(self):
    #     return '<ScarlettListener>'

    def __init__(self, message):
        DBusGMainLoop(set_as_default=True)
        name = dbus.service.BusName(
            'com.example.service', dbus.SessionBus())
        dbus.service.Object.__init__(
            self, name, '/com/example/service')
        self._message = message
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = True
        self.create_dot = False

        self._status_ready = "  ScarlettListener is ready"
        self._status_kw_match = "  ScarlettListener caught a keyword match"
        self._status_cmd_match = "  ScarlettListener caught a command match"
        self._status_stt_failed = "  ScarlettListener hit Max STT failures"
        self._status_cmd_start = "  ScarlettListener emitting start command"
        self._status_cmd_fin = "  ScarlettListener Emitting Command run finish"
        self._status_cmd_cancel = "  ScarlettListener cancel speech Recognition"

        if self.debug:
            # for testing puposes
            self.kw_to_find = ['yo', 'hello', 'man', 'children']
        else:
            self.kw_to_find = self.config.get('scarlett', 'keywords')

    #########################################################
    # Scarlett signals
    #########################################################
    @dbus.service.signal("com.example.service.event")
    def KeywordRecognizedSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))

    @dbus.service.signal("com.example.service.event")
    def CommandRecognizedSignal(self, message, scarlett_sound, scarlett_cmd):
        logger.debug(" sending message: {}".format(message))

    @dbus.service.signal("com.example.service.event")
    def SttFailedSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))

    @dbus.service.signal("com.example.service.event")
    def ListenerCancelSignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))

    @dbus.service.signal("com.example.service.event")
    def ListenerReadySignal(self, message, scarlett_sound):
        logger.debug(" sending message: {}".format(message))

    @dbus.service.signal("com.example.service.event")
    def ConnectedToListener(self, scarlett_plugin):
        pass

    #########################################################
    # Scarlett dbus methods
    #########################################################
    @dbus.service.method("com.example.service.emitKeywordRecognizedSignal",
                         in_signature='',
                         out_signature='s')
    def emitKeywordRecognizedSignal(self):
        global SCARLETT_LISTENING
        # you emit signals by calling the signal's skeleton method
        self.KeywordRecognizedSignal(self._status_kw_match, SCARLETT_LISTENING)
        return SCARLETT_LISTENING

    @dbus.service.method("com.example.service.emitCommandRecognizedSignal",
                         in_signature='',
                         out_signature='s')
    def emitCommandRecognizedSignal(self, command):
        global SCARLETT_RESPONSE
        self.CommandRecognizedSignal(self._status_cmd_match,
                                     SCARLETT_RESPONSE,
                                     command)
        return SCARLETT_RESPONSE

    @dbus.service.method("com.example.service.emitSttFailedSignal",
                         in_signature='',
                         out_signature='s')
    def emitSttFailedSignal(self):
        global SCARLETT_FAILED
        self.SttFailedSignal(self._status_stt_failed, SCARLETT_FAILED)
        return SCARLETT_FAILED

    @dbus.service.method("com.example.service.emitListenerCancelSignal",
                         in_signature='',
                         out_signature='s')
    def emitListenerCancelSignal(self):
        global SCARLETT_CANCEL
        self.ListenerCancelSignal(self._status_cmd_cancel, SCARLETT_CANCEL)
        return SCARLETT_CANCEL

    @dbus.service.method("com.example.service.emitListenerReadySignal",
                         in_signature='',
                         out_signature='s')
    def emitListenerReadySignal(self):
        global SCARLETT_LISTENING
        self.ListenerReadySignal(self._status_ready, SCARLETT_LISTENING)
        return SCARLETT_LISTENING

    @dbus.service.method("com.example.service.emitConnectedToListener",
                         in_signature='',
                         out_signature='s')
    def emitConnectedToListener(self, scarlett_plugin):
        print "  sending message"
        self.ConnectedToListener(scarlett_plugin)
        return " {} is connected to ScarlettListener".format(scarlett_plugin)

    @dbus.service.method("com.example.service.Message",
                         in_signature='',
                         out_signature='s')
    def get_message(self):
        print "  sending message"
        return self._message

    # DISABLED # @dbus.service.method("com.example.service.Quit",
    # DISABLED #                      in_signature='',
    # DISABLED #                      out_signature='')
    # DISABLED # def quit(self):
    # DISABLED #     print "  shutting down"
    # DISABLED #     self.pipeline.set_state(gst.STATE_NULL)
    # DISABLED #     self._loop.quit()

    @dbus.service.method("com.example.service.StatusReady",
                         in_signature='',
                         out_signature='s')
    def listener_ready(self):
        print " {}".format(self._status_ready)
        return self._status_ready

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

    def get_pocketsphinx_definition(self, device, hmm, lm, dic):
        logger.debug("Inside get_pocketsphinx_definition")
        return ['alsasrc device=' +
                device,
                'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',
                'audioconvert',
                'audioresample',
                'audio/x-raw,format=S16LE,channels=1,layout=interleaved',
                'pocketsphinx name=asr bestpath=0',
                'queue leaky=2',
                'fakesink']

    # this function generates the dot file, checks that graphviz in installed and
    # then finally generates a png file, which it then displays
    def on_debug_activate(self):
        dotfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/scarlett-debug-graph.dot"
        pngfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/scarlett-pipeline.png"
        if os.access(dotfile, os.F_OK):
            os.remove(dotfile)
        if os.access(pngfile, os.F_OK):
            os.remove(pngfile)
        gst.DEBUG_BIN_TO_DOT_FILE(self.pipeline,
                                  gst.DEBUG_GRAPH_SHOW_ALL, 'scarlett-debug-graph')
        # check if graphviz is installed with a simple test
        try:
            os.system('/usr/bin/dot' + " -Tpng -o " + pngfile + " " + dotfile)
            # Gtk.show_uri(None, "file://"+pngfile, 0)
        except:
            print "The debug feature requires graphviz (dot) to be installed."
            print "Transmageddon can not find the (dot) binary."

    def result(self, final_hyp):
        """Forward result signals on the bus to the main thread."""
        logger.debug("Inside result function")
        logger.debug("final_hyp: {}".format(final_hyp))
        # logger.debug("Compare: {} {} is {}".format(final_hyp,self.kw_to_find,final_hyp in self.kw_to_find))
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
            logger.debug(
                " Command = {}".format(final_hyp))
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def run_pipeline(self, device=None, hmm=None, lm=None, dict=None):
        pipeline = Gst.parse_launch(' ! '.join(
                                    self.get_pocketsphinx_definition(device,
                                                                     hmm,
                                                                     lm,
                                                                     dict)))

        pocketsphinx = pipeline.get_by_name('asr')
        if hmm:
            pocketsphinx.set_property('hmm', hmm)
        if lm:
            pocketsphinx.set_property('lm', lm)
        if dict:
            pocketsphinx.set_property('dict', dict)

        bus = pipeline.get_bus()

        # Start playing
        pipeline.set_state(Gst.State.PLAYING)

        self.emitListenerReadySignal()

        print "ScarlettListener running..."
        if self.create_dot:
            self.on_debug_activate()

        # Wait until error or EOS
        while True:
            try:
                msg = bus.timed_pop(Gst.CLOCK_TIME_NONE)
                if msg:
                    # if msg.get_structure():
                    #    print(msg.get_structure().to_string())

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
                pipeline.send_event(Gst.Event.new_eos())

        # Free resources
        pipeline.set_state(Gst.State.NULL)
        print "ScarlettListener stopped"

if __name__ == '__main__':
    global logger
    logger = setup_logger()

    sl = ScarlettListener("This is the ScarlettListener")

    LANGUAGE_VERSION = 1473
    HOMEDIR = "/home/pi"
    LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-gstreamer-pocketsphinx-demo".format(
        HOMEDIR)
    LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
    DICT_PATH = "{}/{}.dic".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
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
    parser.add_argument('--dict',
                        default=DICT_PATH,
                        help='Path to a pocketsphinx CMU dictionary file')
    args = parser.parse_args()
    sl.run_pipeline(**vars(args))
