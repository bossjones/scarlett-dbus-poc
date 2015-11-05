#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import threads_init
import gobject
gobject.threads_init()
threads_init()

import pygst
pygst.require('0.10')
import gst

import StringIO
import os
import sys
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
SCARLETT_FAILED = "pi-response.2"


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "(%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red',
        },
        secondary_log_colors={
            'message': {
                'ERROR':    'red',
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

    def __init__(self, message):
        self._message = message
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False

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

    def ready(self):
        self.ps_hmm = self.get_hmm_full_path()
        self.ps_dict = self.get_dict_full_path()
        self.ps_lm = self.get_lm_full_path()
        self.ps_device = self.config.get('audio', 'usb_input_device')
        self.speech_system = self.config.get('speech', 'system')
        self.parse_launch_array = self._get_pocketsphinx_definition(
            self.override_parse)
        self.pipeline = gst.parse_launch(
            ' ! '.join(self.parse_launch_array))

    def run(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus_name = dbus.service.BusName(
            "com.example.service", dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, "/com/example/service")

        self.ready()

        listener = self.pipeline.get_by_name('listener')
        listener.connect('result', self.__result__)
        listener.set_property('configured', True)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        self.pipeline.set_state(gst.STATE_PLAYING)

        self._loop = gobject.MainLoop()
        print "ScarlettListener running..."
        self.emitListenerReadySignal()
        self._loop.run()
        print "ScarlettListener stopped"

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
        # logger.debug(
        #     " {} is connected to ScarlettListener".format(scarlett_plugin))

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
        return self._status_stt_failed

    @dbus.service.method("com.example.service.emitListenerCancelSignal",
                         in_signature='',
                         out_signature='s')
    def emitListenerCancelSignal(self):
        global SCARLETT_CANCEL
        self.ListenerCancelSignal(self._status_cmd_cancel, SCARLETT_CANCEL)
        return self._status_cmd_cancel

    @dbus.service.method("com.example.service.emitListenerReadySignal",
                         in_signature='',
                         out_signature='s')
    def emitListenerReadySignal(self):
        global SCARLETT_LISTENING
        self.ListenerReadySignal(self._status_ready, SCARLETT_LISTENING)
        return self._status_ready

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

    @dbus.service.method("com.example.service.Quit",
                         in_signature='',
                         out_signature='')
    def quit(self):
        print "  shutting down"
        self.pipeline.set_state(gst.STATE_NULL)
        self._loop.quit()

    @dbus.service.method("com.example.service.StatusReady",
                         in_signature='',
                         out_signature='s')
    def listener_ready(self):
        print " {}".format(self._status_ready)
        return self._status_ready

    def scarlett_reset_listen(self):
        self.failed = 0
        self.kw_found = 0

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        pass

    def result(self, hyp, uttid):
        """Forward result signals on the bus to the main thread."""
        logger.debug("Inside result function")
        if hyp in self.kw_to_find:
            logger.debug(
                "HYP-IS-SOMETHING: " +
                hyp +
                "\n\n\n")
            logger.debug(
                "UTTID-IS-SOMETHING:" +
                uttid +
                "\n")
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
                # TODO: Change this to emit text data to main thread
                # ScarlettTalk.speak(
                #     " %s , if you need me, just say my name." %
                #     (self.config.get('scarlett', 'owner')))

    def run_cmd(self, hyp, uttid):
        logger.debug("Inside run_cmd function")
        logger.debug("KEYWORD IDENTIFIED BABY")
        logger.debug(
            "self.kw_found = %i" %
            (self.kw_found))
        if hyp == 'CANCEL':
            self.emitListenerCancelSignal()
            self.cancel_listening()
        else:
            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified
            self.emitCommandRecognizedSignal(hyp)
            logger.debug(
                " Command = {}".format(hyp))
            logger.debug(
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def hello(self):
        print 'hello hello hello!'

    def listen(self, valve, vader):
        logger.debug("Inside listen function")
        # TODO: have this emit pi-listening to mainthread
        # scarlett.basics.voice.play_block('pi-listening')
        valve.set_property('drop', False)
        valve.set_property('drop', True)

    def cancel_listening(self):
        logger.debug("Inside cancel_listening function")
        self.scarlett_reset_listen()
        logger.debug("self.failed = %i" % (self.failed))
        logger.debug(
            "self.keyword_identified = %i" %
            (self.kw_found))

    def get_hmm_full_path(self):
        if os.environ.get('SCARLETT_HMM'):
            _hmm_full_path = os.environ.get('SCARLETT_HMM')
        else:
            _hmm_full_path = self.config.get('pocketsphinx', 'hmm')

        return _hmm_full_path

    def get_lm_full_path(self):
        if os.environ.get('SCARLETT_LM'):
            _lm_full_path = os.environ.get('SCARLETT_LM')
        else:
            _lm_full_path = self.config.get('pocketsphinx', 'lm')

        return _lm_full_path

    def get_dict_full_path(self):
        if os.environ.get('SCARLETT_DICT'):
            _dict_full_path = os.environ.get('SCARLETT_DICT')
        else:
            _dict_full_path = self.config.get('pocketsphinx', 'dict')

        return _dict_full_path

    def get_pipeline(self):
        logger.debug("Inside get_pipeline")
        return self.pipeline

    def get_pipeline_state(self):
        return self.pipeline.get_state()

    def _get_pocketsphinx_definition(self, override_parse):
        logger.debug("Inside _get_pocketsphinx_definition")
        """Return ``pocketsphinx`` definition for :func:`gst.parse_launch`."""
        # default, use what we have set
        if override_parse == '':
            return [
                'alsasrc device=' +
                self.ps_device,
                'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',  # noqa
                'audioconvert',
                'audioresample',
                'audio/x-raw-int, rate=16000, width=16, depth=16, channels=1',
                'audioresample',
                'audio/x-raw-int, rate=8000',
                'vader name=vader auto-threshold=true',
                'pocketsphinx lm=' +
                self.ps_lm +
                ' dict=' +
                self.ps_dict +
                ' hmm=' +
                self.ps_hmm +
                ' name=listener',
                'fakesink dump=1']
            # NOTE, I commented out the refrence to the tee
            # 'fakesink dump=1 t.'
        else:
            return override_parse

    def _get_vader_definition(self):
        logger.debug("Inside _get_vader_definition")
        """Return ``vader`` definition for :func:`gst.parse_launch`."""
        # source: https://github.com/bossjones/eshayari/blob/master/eshayari/application.py # noqa
        # Convert noise level from spin button range [0,32768] to gstreamer
        # element's range [0,1]. Likewise, convert silence from spin button's
        # milliseconds to gstreamer element's nanoseconds.

        # MY DEFAULT VADER DEFINITON WAS: vader name=vader auto-threshold=true
        # vader name=vader auto-threshold=true
        noise = 256 / 32768
        silence = 300 * 1000000
        return ("vader "
                + "name=vader "
                + "auto-threshold=false "
                + "threshold=%.9f " % noise
                + "run-length=%d " % silence
                )

    def _on_vader_start(self, vader, pos):
        logger.debug("Inside _on_vader_start")
        """Send start position as a message on the bus."""
        import gst
        struct = gst.Structure("start")
        pos = pos / 1000000000  # ns to s
        struct.set_value("start", pos)
        vader.post_message(gst.message_new_application(vader, struct))

    def _on_vader_stop(self, vader, pos):
        logger.debug("Inside _on_vader_stop")
        """Send stop position as a message on the bus."""
        import gst
        struct = gst.Structure("stop")
        pos = pos / 1000000000  # ns to s
        struct.set_value("stop", pos)

    def __result__(self, listener, text, uttid):
        """We're inside __result__"""
        logger.debug("Inside __result__")
        import gst
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __partial_result__(self, listener, text, uttid):
        """We're inside __partial_result__"""
        logger.debug("Inside __partial_result__")
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __run_cmd__(self, listener, text, uttid):
        """We're inside __run_cmd__"""
        import gst
        logger.debug("Inside __run_cmd__")
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __application_message__(self, bus, msg):
        msgtype = msg.structure.get_name()
        logger.debug("msgtype: " + msgtype)
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            if self.kw_found == 1:
                self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
            else:
                self.result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'run_cmd':
            self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == gst.MESSAGE_EOS:
            pass
        elif msgtype == gst.MESSAGE_ERROR:
            (err, debug) = msgtype.parse_error()
            logger.debug("Error: %s" % err, debug)
            pass

if __name__ == "__main__":
    global logger
    logger = setup_logger()

    sl = ScarlettListener("This is the ScarlettListener")

    def sigint_handler(*args):
        """Exit on Ctrl+C"""

        # Unregister handler, next Ctrl-C will kill app
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        sl.quit()

    signal.signal(signal.SIGINT, sigint_handler)

    sl.run()
