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

SCARLETT_CANCEL = "pi-cancel"
SCARLETT_LISTENING = "pi-listening"
SCARLETT_RESPONSE = "pi-response"
SCARLETT_FAILED = "pi-response2"

from gettext import gettext as _

gst = Gst

import scarlett_gstutils
import scarlett_config


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


# Create a player
PWD = '/home/pi/dev/bossjones-github/scarlett-dbus-poc'
logger = setup_logger()

gst = Gst


class ScarlettPlayer():

    def __init__(self, sound):
        global PWD
        global logger
        self.loop = GLib.MainLoop()
        self.pipelines_stack  = []

        self._message = 'This is the ScarlettPlayer'
        self.config = scarlett_config.Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0
        self.debug = False
        self.create_dot = False

        # Element playbin automatic plays any sound
        player = gst.element_factory_make("playback", "player")
        self.end_cond = threading.Condition(threading.Lock())

        # Set the uri to the sound
        filename = '%s/static/sounds/%s.wav' % (PWD, sound)
        player.set_property('uri', 'file://%s' % filename)
        self.sound = sound

        # Enable message bus to check for errors in the pipeline
        gst_bus = player.get_bus()

        self.pipelines_stack.append(player)

        logger.debug("ScarlettPlayer __init__ finished")

        self.mainloopthread = scarlett_gstutils.MainloopThread(self.loop)
        self.mainloopthread.start()

        # start pipeline
        player.set_state(Gst.State.PLAYING)

        while True:
            try:
                msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
                if msg:
                    # if msg.get_structure():
                    #    print(msg.get_structure().to_string())

                    if msg.type == Gst.MessageType.EOS:
                        logger.debug("OKAY, Gst.MessageType.EOS: ".format(Gst.MessageType.EOS))
                        p = self.pipelines_stack[0]
                        p.set_state(Gst.State.NULL)
                        self.loop.quit()
                        self.quit()
                        break
                    if msg.type == Gst.MessageType.ERROR:
                        logger.debug("OKAY, Gst.MessageType.ERROR: ".format(Gst.MessageType.ERROR))
                        p = self.pipelines_stack[0]
                        p.set_state(Gst.State.NULL)
                        self.loop.quit()
                        self.end_reached = True
                        err, debug = msg.parse_error()
                        self.error_msg = "Error: %s" % err, debug
                        self.end_cond.notify()
                        self.end_cond.release()
                        self.quit()
                        break
            except KeyboardInterrupt:
                player.send_event(Gst.Event.new_eos())

        # Free resources
        player.set_state(Gst.State.NULL)
        print "ScarlettPlayer stopped"
    #
    # def release(self):
    #     if hasattr(self, 'eod') and hasattr(self, 'loop'):
    #         self.end_cond.acquire()
    #         while not hasattr(self, 'end_reached'):
    #             self.end_cond.wait()
    #         self.end_cond.release()
    #     if hasattr(self, 'error_msg'):
    #         raise IOError(self.error_msg)

    def run(self):
        logger.debug("ScarlettPlayer sound: {}".format(self.sound))
        # self.player.set_state(gst.STATE_PLAYING)
        self.loop.run()
    #
    # def on_message(self, bus, message):
    #     pp = pprint.PrettyPrinter(indent=4)
    #     pp.pprint(bus)
    #     pp.pprint(message)
    #     t = message.type
    #     if t == gst.MESSAGE_EOS:
    #         logger.debug("OKAY, MESSAGE_EOS: ".format(gst.MESSAGE_EOS))
    #         self.player.set_state(gst.STATE_NULL)
    #         self.loop.quit()
    #         self.quit()
    #     elif t == gst.MESSAGE_ERROR:
    #         logger.debug("OKAY, MESSAGE_ERROR: ".format(gst.MESSAGE_ERROR))
    #         self.player.set_state(gst.STATE_NULL)
    #         err, debug = message.parse_error()
    #         print "Error: %s" % err, debug
    #         self.loop.quit()
    #         self.quit()
    #
    # def finish_request(self):
    #     self.player.set_state(gst.STATE_NULL)
    #     self.loop.quit()
    #     self.quit()
    #     time.sleep(2)
    #     return
    #
    # def _on_message_cb(self, bus, message):
    #     if self.debug:
    #         pp = pprint.PrettyPrinter(indent=4)
    #         pp.pprint(bus)
    #         pp.pprint(message)
    #     t = message.type
    #     if t == gst.MESSAGE_EOS:
    #         logger.debug("OKAY, MESSAGE_EOS: ".format(gst.MESSAGE_EOS))
    #         self.end_cond.acquire()
    #         self.player.set_state(gst.STATE_NULL)
    #         self.loop.quit()
    #         self.end_reached = True
    #         self.end_cond.notify()
    #         self.end_cond.release()
    #         self.quit()
    #
    #     elif t == gst.MESSAGE_ERROR:
    #         logger.debug("OKAY, MESSAGE_ERROR: ".format(gst.MESSAGE_ERROR))
    #         self.end_cond.acquire()
    #         self.player.set_state(gst.STATE_NULL)
    #         self.loop.quit()
    #         self.end_reached = True
    #         err, debug = message.parse_error()
    #         self.error_msg = "Error: %s" % err, debug
    #         self.end_cond.notify()
    #         self.end_cond.release()
    #         self.quit()
    #
    # def on_finish(self, bus, message):
    #     logger.debug("OKAY, on_finish. Setting state to STATE_NULL")
    #     self.finish_request()
    #
    # def on_error(self, bus, message):
    #     logger.debug("OKAY, on_error. Setting state to STATE_NULL")
    #     self.finish_request()

    def quit(self):
        logger.debug("  shutting down ScarlettPlayer")

    #
    # def run_pipeline(self):
    #     pipeline = Gst.parse_launch(' ! '.join(
    #                                 self.get_pocketsphinx_definition(device,
    #                                                                  hmm,
    #                                                                  lm,
    #                                                                  dict)))
    #     self.pipelines_stack.append(pipeline)
    #
    #     pocketsphinx = pipeline.get_by_name('asr')
    #     if hmm:
    #         pocketsphinx.set_property('hmm', hmm)
    #     if lm:
    #         pocketsphinx.set_property('lm', lm)
    #     if dict:
    #         pocketsphinx.set_property('dict', dict)
    #
    #     gst_bus = pipeline.get_bus()
    #
    #     # Start playing
    #     pipeline.set_state(Gst.State.PLAYING)
    #
    #     self.emitListenerReadySignal()
    #
    #     print "ScarlettListener running..."
    #     if self.create_dot:
    #         self.on_debug_activate()
    #
    #     # Wait until error or EOS
    #     while True:
    #         try:
    #             msg = gst_bus.timed_pop(Gst.CLOCK_TIME_NONE)
    #             if msg:
    #                 # if msg.get_structure():
    #                 #    print(msg.get_structure().to_string())
    #
    #                 if msg.type == Gst.MessageType.EOS:
    #                     break
    #                 struct = msg.get_structure()
    #                 if struct and struct.get_name() == 'pocketsphinx':
    #                     if struct['final']:
    #                         logger.info(struct['hypothesis'])
    #                         if self.kw_found == 1:
    #                             # If keyword is set AND qualifier
    #                             # then perform action
    #                             self.run_cmd(struct['hypothesis'])
    #                         else:
    #                             # If it's the main keyword,
    #                             # set values wait for qualifier
    #                             self.result(struct['hypothesis'])
    #         except KeyboardInterrupt:
    #             pipeline.send_event(Gst.Event.new_eos())
    #
    #     # Free resources
    #     pipeline.set_state(Gst.State.NULL)
    #     print "ScarlettListener stopped"


# if __name__ == '__main__':
#     global logger
#     logger = setup_logger()
#
#     from pydbus import SessionBus
#     bus = SessionBus()
#     bus.own_name(name = 'org.scarlett')
#     sl = ScarlettListener(bus=bus.con, path='/org/scarlett/Listener')
#
#     LANGUAGE_VERSION = 1473
#     HOMEDIR = "/home/pi"
#     LANGUAGE_FILE_HOME = "{}/dev/bossjones-github/scarlett-gstreamer-pocketsphinx-demo".format(
#         HOMEDIR)
#     LM_PATH = "{}/{}.lm".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
#     DICT_PATH = "{}/{}.dic".format(LANGUAGE_FILE_HOME, LANGUAGE_VERSION)
#     HMM_PATH = "{}/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us".format(
#         HOMEDIR)
#     bestpath = 0
#     PS_DEVICE = 'plughw:CARD=Device,DEV=0'
#
#     parser = argparse.ArgumentParser(description='Recognize speech from audio')
#     parser.add_argument('--device',
#                         default=PS_DEVICE,
#                         help='Pocketsphinx audio source device')
#     parser.add_argument('--hmm',
#                         default=HMM_PATH,
#                         help='Path to a pocketsphinx HMM data directory')
#     parser.add_argument('--lm',
#                         default=LM_PATH,
#                         help='Path to a pocketsphinx language model file')
#     parser.add_argument('--dict',
#                         default=DICT_PATH,
#                         help='Path to a pocketsphinx CMU dictionary file')
#     args = parser.parse_args()
#
#     def sigint_handler(*args):
#         """Exit on Ctrl+C"""
#
#         # Unregister handler, next Ctrl-C will kill app
#         # TODO: figure out if this is really needed or not
#         signal.signal(signal.SIGINT, signal.SIG_DFL)
#
#         sl.quit()
#
#     signal.signal(signal.SIGINT, sigint_handler)
#
#     sl.run_pipeline(**vars(args))
