#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
import time

SCARLETT_DEBUG = 1

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


class Server(object):

    def __init__(self, bus, path):
        self.loop = GLib.MainLoop()
        self.dbus_stack = []
        self.pipelines_stack = []

        self._message = 'This is the DBusServer'
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
            pp.pprint("BOSSJONES sig BOYYYYY")
            pp.pprint(sig)
            # if UNIX_FD
            if sig is 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])

        result = getattr(self, method_name)(*args)

        # logger.debug("BOSSJONES type(result) = {}".format(type(result)))
        pp.pprint("BOSSJONES type(result) BOYYYYY")
        pp.pprint(type(result))

        if type(result) is list:
            result = tuple(result)
        elif type(result) is not tuple:
            result = (result,)

        out_args = self.method_outargs[method_name]
        if out_args != '()':
            logger.debug("Inside out_args in != ()")
            pp.pprint(out_args)
            logger.debug("Inside result != ()")
            pp.pprint(result)
            invocation.return_value(GLib.Variant(out_args, result))


class ScarlettListener(Server):
    '''
<node>
  <interface name='org.scarlett.Listener1'>
    <method name='emitListenerReadySignal'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <signal name='ListenerReadySignal'>
      <arg type='(ss)' name='listener_rdy_status' direction='out'/>
    </signal>
  </interface>
</node>
    '''
    LISTENER_IFACE = 'org.scarlett.Listener'
    LISTENER_PLAYER_IFACE = 'org.scarlett.Listener.Player'
    LISTENER_TRACKLIST_IFACE = 'org.scarlett.Listener.TrackList'
    LISTENER_PLAYLISTS_IFACE = 'org.scarlett.Listener.Playlists'
    LISTENER_EVENTS_IFACE = 'org.scarlett.Listener.event'

    def ListenerReadySignal(self, message, scarlett_sound):
        logger.debug(f" sending message: {message}")
        bus = self.dbus_stack[0]
        listener_rdy_status = GLib.Variant("(ss)", (message, scarlett_sound))
        bus.emit_signal(None,
                        '/org/scarlett/Listener',
                        'org.scarlett.Listener',
                        'ListenerReadySignal',
                        listener_rdy_status)

    #########################################################
    # Scarlett dbus methods in = func args, out = return values
    #########################################################

    def emitListenerReadySignal(self):
        global SCARLETT_LISTENING
        self.ListenerReadySignal(self._status_ready, SCARLETT_LISTENING)
        return SCARLETT_LISTENING

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

    # NOTE: This function generates the dot file, checks that graphviz in installed and
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
        logger.debug(f"final_hyp: {final_hyp}")
        pp.pprint(final_hyp)
        logger.debug(f"kw_to_find: {self.kw_to_find}")
        if final_hyp in self.kw_to_find:
            logger.debug(
                "HYP-IS-SOMETHING: " +
                final_hyp +
                "\n\n\n")
            self.failed = 0
            self.kw_found = 1
        else:
            failed_temp = self.failed + 1
            self.failed = failed_temp
            logger.debug(
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.scarlett_reset_listen()

    def run_cmd(self, final_hyp):
        logger.debug("Inside run_cmd function")
        logger.debug("KEYWORD IDENTIFIED BABY")
        logger.debug(
            "self.kw_found = %i" %
            (self.kw_found))
        if final_hyp == 'CANCEL':
            self.cancel_listening()
        else:
            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified
            logger.debug(f" Command = {final_hyp}")
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def run_pipeline(self, device=None, hmm=None, lm=None, dict=None):
        pipeline = Gst.parse_launch(' ! '.join(
                                    self.get_pocketsphinx_definition(device,
                                                                     hmm,
                                                                     lm,
                                                                     dict)))
        self.pipelines_stack.append(pipeline)

        pocketsphinx = pipeline.get_by_name('asr')
        if hmm:
            pocketsphinx.set_property('hmm', hmm)
        if lm:
            pocketsphinx.set_property('lm', lm)
        if dict:
            pocketsphinx.set_property('dict', dict)

        gst_bus = pipeline.get_bus()

        # Start playing
        pipeline.set_state(Gst.State.PLAYING)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        self.emitListenerReadySignal()

        time.sleep(5)

        print "ScarlettListener running..."
        if self.create_dot:
            self.on_debug_activate()

        # Wait until error or EOS
        while True:
            try:
                msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
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
    parser.add_argument('--dict',
                        default=DICT_PATH,
                        help='Path to a pocketsphinx CMU dictionary file')
    args = parser.parse_args()

    def sigint_handler(*args):
        """Exit on Ctrl+C"""

        # Unregister handler, next Ctrl-C will kill app
        # TODO: figure out if this is really needed or not
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        sl.quit()

    signal.signal(signal.SIGINT, sigint_handler)

    sl.run_pipeline(**vars(args))
