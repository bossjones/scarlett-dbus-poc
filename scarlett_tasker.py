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
import scarlett_constants

import threading
import time

import scarlett_player
import scarlett_speaker
import scarlett_forecast
import scarlett_config


def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "%(asctime)s.%(msecs)03d (%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt='%Y-%m-%d,%H:%M:%S',
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
        self._quit = service.get_dbus_method(
            'quit', 'com.example.service.Quit')
        self._tasker_connected = service.get_dbus_method(
            'emitConnectedToListener',
            'com.example.service.emitConnectedToListener')

        self.config = scarlett_config.Config()

        # Function which will run when signal is received
        # def callback_function(*args):
        #     logger.debug('Received something .. ', str(args))

        # def catchall_handler(*args, **kwargs):
        #     logger.debug("catchall_handler PrettyPrinter: ")
        #     pp = pprint.PrettyPrinter(indent=4)
        #     pp.pprint(args)

        def wait_for_t(t):
            if not t.is_alive():
                # This won't block, since the thread isn't alive anymore
                t.join()
                print 'waiting.....'
                # Do whatever else you would do when join()
                # (or maybe collega_GUI?) returns
            else:
                gobject.timeout_add(200, wait_for_t, t)

        def player_cb(*args, **kwargs):
            logger.debug("player_cb PrettyPrinter: ")
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(args)
            msg, scarlett_sound = args
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))

            # Our thread will run start_listening
            scarlett_player.ScarlettPlayer(scarlett_sound)

        def command_cb(*args, **kwargs):
            logger.debug("player_cb PrettyPrinter: ")
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(args)
            msg, scarlett_sound, command = args
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))
            logger.warning(" command: {}".format(command))

            # play sound

            # Our thread will run start_listening
            scarlett_player.ScarlettPlayer(scarlett_sound)

            if command in scarlett_constants.FORECAST_CMDS.keys():

                fio_hourly, fio_summary, fio_day = text = scarlett_forecast.ScarlettForecast(
                    self.config, command).api()
                logger.info(" Lets try putting these in one sentance:")
                logger.info(" text: {}".format(text))
                logger.warning(" fio_hourly: {}".format(fio_hourly))
                logger.warning(" fio_summary: {}".format(fio_summary))
                logger.warning(" fio_day: {}".format(fio_day))
                logger.debug(" fio_hourly. fio_summary. fio_day. =  {}. {}. {}.".format(
                    fio_hourly, fio_summary, fio_day))

                # if text > 1:
#
                # Our thread will run start_listening
                # Lets have the threads wait before doing the next thing
                # see this: http://stackoverflow.com/questions/26172107/gobject-idle-add-thread-join-and-my-program-hangs
                #     speaker_thread = threading.Thread(target=scarlett_speaker.ScarlettSpeaker(command).run())
                #     speaker_thread.daemon = True
                #     speaker_thread.start()

        # SIGNAL: When someone says Scarlett
        bus.add_signal_receiver(player_cb,
                                dbus_interface='com.example.service.event',
                                signal_name='KeywordRecognizedSignal'
                                )
        bus.add_signal_receiver(command_cb,
                                dbus_interface='com.example.service.event',
                                signal_name='CommandRecognizedSignal'
                                )
        bus.add_signal_receiver(player_cb,
                                dbus_interface='com.example.service.event',
                                signal_name='SttFailedSignal'
                                )
        bus.add_signal_receiver(player_cb,
                                dbus_interface='com.example.service.event',
                                signal_name='ListenerCancelSignal'
                                )
        # bus.add_signal_receiver(catchall_handler,
        #                         dbus_interface='com.example.service.event',
        #                         signal_name='ConnectedToListener'
        #                         )

    def go(self):
        logger.debug("ScarlettTasker running...")
        self._loop.run()
        logger.debug("ScarlettTasker stopped")

    def run(self):
        logger.debug(
            "{}".format(self._tasker_connected(ScarlettTasker().__class__.__name__)))

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
