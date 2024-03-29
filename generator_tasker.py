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
from gi.repository import GLib
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

import generator_utils
from generator_utils import trace, abort_on_exception, _IdleObject
import generator_player
import generator_speaker
import generator_commands

import logging
logger = logging.getLogger('scarlettlogger')


STATIC_SOUNDS_PATH = '/home/pi/dev/bossjones-github/scarlett-dbus-poc/static/sounds'
# /pi-listening.wav

# loop = GObject.MainLoop()
loop = GLib.MainLoop()

try:
    from rfoo.utils import rconsole
    rconsole.spawn_server()
except ImportError:
    logger.debug("No socket opened for debugging -> please install rfoo")


class SoundType:
    """Enum of Player Types."""
    SCARLETT_CANCEL = "pi-cancel"
    SCARLETT_LISTENING = "pi-listening"
    SCARLETT_RESPONSE = "pi-response"
    SCARLETT_FAILED = "pi-response2"

    @staticmethod
    def get_path(sound_type):
        return [f"{STATIC_SOUNDS_PATH}/{sound_type}.wav"]


class SpeakerType:
    """Enum of Player Types."""

    @staticmethod
    def speaker_to_array(sentance):
        return [f"{sentance}"]


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
                                         iface="org.scarlett.Listener",
                                         signal="SttFailedSignal",
                                         object="/org/scarlett/Listener",
                                         arg0=None,
                                         flags=0,
                                         signal_fired=player_cb)

        ss_rdy_signal = bus.subscribe(sender=None,
                                      iface="org.scarlett.Listener",
                                      signal="ListenerReadySignal",
                                      object="/org/scarlett/Listener",
                                      arg0=None,
                                      flags=0,
                                      signal_fired=player_cb)

        ss_kw_rec_signal = bus.subscribe(sender=None,
                                         iface="org.scarlett.Listener",
                                         signal="KeywordRecognizedSignal",
                                         object="/org/scarlett/Listener",
                                         arg0=None,
                                         flags=0,
                                         signal_fired=player_cb)

        ss_cmd_rec_signal = bus.subscribe(sender=None,
                                          iface="org.scarlett.Listener",
                                          signal="CommandRecognizedSignal",
                                          object="/org/scarlett/Listener",
                                          arg0=None,
                                          flags=0,
                                          signal_fired=command_cb)

        ss_cancel_signal = bus.subscribe(sender=None,
                                         iface="org.scarlett.Listener",
                                         signal="ListenerCancelSignal",
                                         object="/org/scarlett/Listener",
                                         arg0=None,
                                         flags=0,
                                         signal_fired=player_cb)

        pp.pprint((ss_failed_signal,
                   ss_rdy_signal,
                   ss_kw_rec_signal,
                   ss_cmd_rec_signal,
                   ss_cancel_signal))

        logger.debug(f"ss_failed_signal: {ss_failed_signal}")
        logger.debug(f"ss_rdy_signal: {ss_rdy_signal}")
        logger.debug(f"ss_kw_rec_signal: {ss_kw_rec_signal}")
        logger.debug(f"ss_cmd_rec_signal: {ss_cmd_rec_signal}")
        logger.debug(f"ss_cancel_signal: {ss_cancel_signal}")

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


def signal_handler_player_thread(scarlett_sound):
    '''No-Op Function to handle playing Gstreamer.'''

    def function_calling_player_gst(event, *args, **kwargs):
        player_run = True
        logger.info('BEGIN PLAYING WITH SCARLETTPLAYER')
        if player_run:
            wavefile = SoundType.get_path(scarlett_sound)
            for path in wavefile:
                path = os.path.abspath(os.path.expanduser(path))
                with generator_player.ScarlettPlayer(path) as f:
                    print(f.channels)
                    print(f.samplerate)
                    print(f.duration)
                    for s in f:
                        yield
        event.set()
        wavefile = None
        player_run = False
        logger.info('END PLAYING WITH SCARLETTPLAYER INSIDE IF')
        event.clear()

    event = threading.Event()
    logger.info('event = threading.Event()')
    GObject.idle_add(function_calling_player_gst, event, priority=GLib.PRIORITY_HIGH)
    logger.info('BEFORE event.wait()')
    event.wait()
    logger.info('END PLAYING WITH SCARLETTPLAYER INSIDE IF')


@abort_on_exception
def signal_handler_speaker_thread():

    def function_calling_speaker(event, result, tts_list):
        for scarlett_text in tts_list:
            with generator_utils.time_logger('Scarlett Speaks'):
                generator_speaker.ScarlettSpeaker(text_to_speak=scarlett_text,
                                                  wavpath="/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav")
        event.set()

# def signal_handler_speaker_thread(scarlett_sound):
#     '''No-Op Function to handle playing Gstreamer.'''
#     Tracer()()
#
#     def function_calling_player_gst(event, *args, **kwargs):
#         player_run = True
#         logger.info('BEGIN PLAYING WITH SCARLETTPLAYER')
#         if player_run:
#             wavefile = SoundType.get_path(scarlett_sound)
#             for path in wavefile:
#                 path = os.path.abspath(os.path.expanduser(path))
#                 with generator_player.ScarlettPlayer(path) as f:
#                     print(f.channels)
#                     print(f.samplerate)
#                     print(f.duration)
#                     for s in f:
#                         yield
#         event.set()
#         wavefile = None
#         player_run = False
#         logger.info('END PLAYING WITH SCARLETTPLAYER INSIDE IF')
#         event.clear()
#
#     event = threading.Event()
#     logger.info('event = threading.Event()')
#     GObject.idle_add(function_calling_player_gst, event, priority=GLib.PRIORITY_HIGH)
#     logger.info('BEFORE event.wait()')
#     event.wait()
#     logger.info('END PLAYING WITH SCARLETTPLAYER INSIDE IF')


@abort_on_exception
def fake_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("fake_cb")


def print_keyword_args(**kwargs):
    # kwargs is a dict of the keyword args passed to the function
    for key, value in kwargs.iteritems():
        print(f"{key} = {value}")


@abort_on_exception
def player_cb(*args, **kwargs):
    if SCARLETT_DEBUG:
        logger.debug("player_cb PrettyPrinter: ")
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(args)
        # MAR 13 2016
        logger.debug("player_cb kwargs")
        print_keyword_args(**kwargs)
        # (con=<DBusConnection object at 0x7f3fba21f0f0 (GDBusConnection at 0x2ede000)>,
        # sender=':1.0',
        # object='/org/scarlett/Listener',
        # iface='org.scarlett.Listener',
        # signal='CommandRecognizedSignal',
        # params=GLib.Variant('(sss)', ('  ScarlettListener caugh...ommand match', 'pi-response', 'what time is it')))

        # NOTE: THIS IS WHAT FIXED THE GENERATOR NONSENSE
        # source: https://www.python.org/dev/peps/pep-0343/
        def player_generator_func():
            for path in wavefile:
                path = os.path.abspath(os.path.expanduser(path))
                yield True
                print("for path in wavefile")
                p = generator_player.ScarlettPlayer(path, False)
                while True:
                    try:
                        yield p.next()
                    finally:
                        time.sleep(p.duration)
                        p.close(force=True)
                        yield False

        def run_player(function):
            gen = function()
            GObject.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_HIGH)

    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug("Type v: {}".format(type(v)))
            logger.debug("Type i: {}".format(type(i)))
        if isinstance(v, tuple):
            if SCARLETT_DEBUG:
                logger.debug(
                    "THIS SHOULD BE A Tuple now: {}".format(v))
            msg, scarlett_sound = v
            logger.warning(" msg: {}".format(msg))
            logger.warning(
                " scarlett_sound: {}".format(scarlett_sound))
            # player_run = True
            # logger.info('BEGIN PLAYING WITH SCARLETTPLAYER')
            # wavefile = SoundType.get_path(scarlett_sound)
            # Tracer()()
            # DISABLED # signal_handler_player_thread(scarlett_sound)

            wavefile = SoundType.get_path(scarlett_sound)
            run_player_result = run_player(player_generator_func)
            # return True
            # if player_run:
            #     wavefile = SoundType.get_path(scarlett_sound)
            #     for path in wavefile:
            #         path = os.path.abspath(os.path.expanduser(path))
            #         with generator_player.ScarlettPlayer(path) as f:
            #             print(f.channels)
            #             print(f.samplerate)
            #             print(f.duration)
            #             for s in f:
            #                 pass
            #     wavefile = None
            #     player_run = False
            #     logger.info('END PLAYING WITH SCARLETTPLAYER INSIDE IF')
            #     return True
            logger.info('END PLAYING WITH SCARLETTPLAYER OUTSIDE IF')
        else:
            logger.debug("THIS IS NOT A GLib.Variant: {} - TYPE {}".format(v, type(v)))


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
        # (con=<DBusConnection object at 0x7f3fba21f0f0 (GDBusConnection at 0x2ede000)>,
        # sender=':1.0',
        # object='/org/scarlett/Listener',
        # iface='org.scarlett.Listener',
        # signal='CommandRecognizedSignal',
        # params=GLib.Variant('(sss)', ('  ScarlettListener caugh...ommand match', 'pi-response', 'what time is it')))

        # NOTE: THIS IS WHAT FIXED THE GENERATOR NONSENSE
        # source: https://www.python.org/dev/peps/pep-0343/
    def player_generator_func():
        for path in wavefile:
            path = os.path.abspath(os.path.expanduser(path))
            yield True
            print("for path in wavefile")
            p = generator_player.ScarlettPlayer(path, False)
            while True:
                try:
                    yield p.next()
                finally:
                    time.sleep(p.duration)
                    p.close(force=True)
                    yield False

    def run_player(function):
        gen = function()
        GObject.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_HIGH)


    def speaker_generator_func():
        for scarlett_text in tts_list:
            yield True
            print("scarlett_text in tts_list")
            _wavepath = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav"
            s = generator_speaker.ScarlettSpeaker(text_to_speak=scarlett_text,
                                                  wavpath=_wavepath,
                                                  skip_player=True)
            p = generator_player.ScarlettPlayer(_wavepath, False)
            logger.error("Duration: p.duration: {}".format(p.duration))
            while True:
                try:
                    yield p.next()
                finally:
                    time.sleep(p.duration)
                    p.close(force=True)
                    s.close(force=True)
                    yield False

    def run_speaker(function):
        gen = function()
        GObject.idle_add(lambda: next(gen, False), priority=GLib.PRIORITY_HIGH)

    for i, v in enumerate(args):
        if SCARLETT_DEBUG:
            logger.debug("Type v: {}".format(type(v)))
            logger.debug("Type i: {}".format(type(i)))
        if isinstance(v, tuple):
            if SCARLETT_DEBUG:
                logger.debug(
                    "THIS SHOULD BE A Tuple now: {}".format(v))
            msg, scarlett_sound, command = v
            logger.warning(" msg: {}".format(msg))
            logger.warning(
                " scarlett_sound: {}".format(scarlett_sound))
            logger.warning(" command: {}".format(command))

            # 1. play sound first
            wavefile = SoundType.get_path(scarlett_sound)
            run_player_result = run_player(player_generator_func)

            # 2. Perform command
            command_run_results = generator_commands.Command.check_cmd(command_tuple=v)

            # 3. Verify it is not a command NO_OP
            if command_run_results == '__SCARLETT_NO_OP__':
                logger.error("__SCARLETT_NO_OP__")
                return False

            # 4. Scarlett Speaks
            tts_list = SpeakerType.speaker_to_array(command_run_results)
            run_speaker_result = run_speaker(speaker_generator_func)

            # 5. Emit signal to reset keyword match ( need to implement this )
            bus = SessionBus()
            ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')  # NOQA
            time.sleep(1)
            ss.emitListenerCancelSignal()
            # 6. Finished call back
        else:
            logger.debug("THIS IS NOT A GLib.Variant: {} - TYPE {}".format(v, type(v)))

if __name__ == "__main__":
    _INSTANCE = st = ScarlettTasker()
    # loop.run()
