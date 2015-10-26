#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# NOTE: dbus signals have no return value
# NOTE: dbus methods can return a value

import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import threads_init, DBusGMainLoop
import gobject
gobject.threads_init()
threads_init()
DBusGMainLoop(set_as_default=True)

import pygst
pygst.require('0.10')
import gst

import StringIO
import os
import sys
import re
import ConfigParser
import signal
import pprint

from dbus import DBusException

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

from colorlog import ColoredFormatter

import logging

import threading
import time

import scarlett_player


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


class ScarlettTasker():

    def __init__(self):
        self._loop = gobject.MainLoop()
        bus = dbus.SessionBus()

        # NOTE: This is a proxy dbus command
        service = bus.get_object('com.example.service', "/com/example/service")
        self._message = service.get_dbus_method(
            'get_message', 'com.example.service.Message')
        self._quit = service.get_dbus_method(
            'quit', 'com.example.service.Quit')
        self._status_ready = service.get_dbus_method(
            'emitListenerReadySignal',
            'com.example.service.emitListenerReadySignal')
        self._tasker_connected = service.get_dbus_method(
            'emitConnectedToListener',
            'com.example.service.emitConnectedToListener')

        # Function which will run when signal is received
        def callback_function(*args):
            logger.debug('Received something .. ', str(args))

        def catchall_handler(*args, **kwargs):
            logger.debug("catchall_handler PrettyPrinter: ")
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(args)

        def player_cb(*args, **kwargs):
            logger.debug("player_cb PrettyPrinter: ")
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(args)
            msg, scarlett_sound = args
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))

            # Our thread will run start_listening
            thread = threading.Thread(target=scarlett_player.ScarlettPlayer(scarlett_sound).run())
            thread.daemon = True
            thread.start()

        # SIGNAL: When someone says Scarlett
        bus.add_signal_receiver(player_cb,
                                dbus_interface='com.example.service.event',
                                signal_name='KeywordRecognizedSignal'
                                )
        bus.add_signal_receiver(catchall_handler,
                                dbus_interface='com.example.service.event',
                                signal_name='CommandRecognizedSignal'
                                )
        bus.add_signal_receiver(catchall_handler,
                                dbus_interface='com.example.service.event',
                                signal_name='SttFailedSignal'
                                )
        bus.add_signal_receiver(catchall_handler,
                                dbus_interface='com.example.service.event',
                                signal_name='ListenerCancelSignal'
                                )
        bus.add_signal_receiver(catchall_handler,
                                dbus_interface='com.example.service.event',
                                signal_name='ConnectedToListener'
                                )

    def go(self):
        logger.debug("ScarlettTasker running...")
        self._loop.run()
        logger.debug("ScarlettTasker stopped")

    def run(self):
        logger.debug(
            "{}".format(self._tasker_connected(ScarlettTasker().__class__.__name__)))
        logger.debug("Mesage from Master service: {}".format(self._message()))

    def quit(self):
        logger.debug("  shutting down ScarlettTasker")
        self._loop.quit()
        self._quit()

if __name__ == "__main__":
    logger = setup_logger()
    global logger

    st = ScarlettTasker()

    def sigint_handler(*args):
        """Exit on Ctrl+C"""

        # Unregister handler, next Ctrl-C will kill app
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        st.quit()

    signal.signal(signal.SIGINT, sigint_handler)

    st.run()

    # Our thread will run start_listening
    thread = threading.Thread(target=st.go)
    thread.daemon = True              # This makes sure that CTRL+C works
    thread.start()

    stored_exception = None

    # And our program will continue in this pointless loop
    # DBusException
    # KeyboardInterrupt
    while True:
        try:
            time.sleep(1)
            logger.info("tralala")
        except DBusException:
            stored_exception = sys.exc_info()

    logger.debug('Bye')

    if stored_exception:
        raise stored_exception[0], stored_exception[1], stored_exception[2]

    sys.exit()
