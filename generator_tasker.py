#!/usr/bin/env python  # NOQA
# -*- coding: UTF-8 -*-
from __future__ import print_function

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

import pprint
pp = pprint.PrettyPrinter(indent=4)

import gi
# gi.require_version('Gtk', '3.0')
# gi.require_version('Gst', '1.0')
from gi.repository import GObject
# from gi.repository import Gst
# from gi.repository import GLib
# from gi.repository import Gio
# from gi.repository import Gtk
import threading

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

import traceback
from functools import wraps
import Queue
from pydbus import SessionBus

from generator_utils import trace, abort_on_exception
import generator_player
import generator_speaker

import logging
logger = logging.getLogger('scarlettlogger')


STATIC_SOUNDS_PATH = '/home/pi/dev/bossjones-github/scarlett-dbus-poc/static/sounds'
# /pi-listening.wav

loop = GObject.MainLoop()


class SoundType:
    """Enum of Player Types."""
    SCARLETT_CANCEL = "pi-cancel"
    SCARLETT_LISTENING = "pi-listening"
    SCARLETT_RESPONSE = "pi-response"
    SCARLETT_FAILED = "pi-response2"

    def get_path(self, sound_type):
        return ["{}/{}/wav".format(STATIC_SOUNDS_PATH, sound_type)]


class SpeakerType:
    """Enum of Player Types."""
    def speaker_to_array(self, sentance):
        return ["{}".format(sentance)]


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




class ScarlettTasker(_IdleObject):

    @abort_on_exception
    def __init__(self, *args):
        _IdleObject.__init__(self)
        context = GObject.MainContext.default()

        self.bucket = bucket = Queue.Queue()  # NOQA
        self.hello = None

        # with SessionBus() as bus:
        bus = SessionBus()
        ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')  # NOQA
        time.sleep(1)

        ss_failed_signal = bus.subscribe(sender=None,
                                         # iface="org.scarlett.Listener1",
                                         iface=None,
                                         #  object="SttFailedSignal",
                                         object="/org/scarlett/Listener",
                                         arg0=None,
                                         flags=0,
                                         signal_fired=player_cb)

        ss_rdy_signal = ss.ListenerReadySignal.connect(player_cb)
        ss_kw_rec_signal = ss.KeywordRecognizedSignal.connect(player_cb)
        ss_cmd_rec_signal = ss.CommandRecognizedSignal.connect(command_cb)
        ss_cancel_signal = ss.ListenerCancelSignal.connect(player_cb)

        pp.pprint((ss_failed_signal,
                  ss_rdy_signal,
                  ss_kw_rec_signal,
                  ss_cmd_rec_signal,
                  ss_cancel_signal))

        logger.debug("ss_failed_signal: {}".format(ss_failed_signal))
        logger.debug("ss_rdy_signal: {}".format(ss_rdy_signal))
        logger.debug("ss_kw_rec_signal: {}".format(ss_kw_rec_signal))
        logger.debug("ss_cmd_rec_signal: {}".format(ss_cmd_rec_signal))
        logger.debug("ss_cancel_signal: {}".format(ss_cancel_signal))

        ss.emitConnectedToListener('ScarlettTasker')
        loop.run()

        # THE ACTUAL THREAD BIT
        # self.manager = FooThreadManager(3)

        try:
            print("ScarlettTasker Thread Started")
        except Exception:
            ss_failed_signal.disconnect()
            ss_rdy_signal.disconnect()
            ss_kw_rec_signal.disconnect()
            ss_cmd_rec_signal.disconnect()
            ss_cancel_signal.disconnect()
            loop.quit()
            self.bucket.put(sys.exc_info())
            raise


@abort_on_exception
def fake_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("fake_cb")

def print_keyword_args(**kwargs):
    # kwargs is a dict of the keyword args passed to the function
    for key, value in kwargs.iteritems():
        print("%s = %s" % (key, value))


@abort_on_exception
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
            player_run = True
            if player_run:
                wavefile = SoundType.get_path(scarlett_sound)
                for path in wavefile:
                    path = os.path.abspath(os.path.expanduser(path))
                    with generator_player.ScarlettPlayer(path) as f:
                        print(f.channels)
                        print(f.samplerate)
                        print(f.duration)
                        for s in f:
                            pass
                wavefile = None
                player_run = False


# NOTE: enumerate req to iterate through tuple and find GVariant
# @trace
@abort_on_exception
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
            command_run = True
            if command_run:
                tts_list = SpeakerType.speaker_to_array('Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands')
                for scarlett_text in tts_list:
                    with generator_speaker.time_logger('Scarlett Speaks'):
                        generator_speaker.ScarlettSpeaker(text_to_speak=scarlett_text,
                                                          wavpath="/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav")
                tts_list = None
                command_run = False

if __name__ == "__main__":
    _INSTANCE = st = ScarlettTasker()
    # loop.run()
