#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# NOTE: dbus signals have no return value
# NOTE: dbus methods can return a value

# import dbus
# import dbus.service
# import dbus.mainloop.glib
# from dbus.mainloop.glib import threads_init, DBusGMainLoop
# import gobject
# gobject.threads_init()
# threads_init()
# DBusGMainLoop(set_as_default=True)

# import pygst
# pygst.require('0.10')
# import gst

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from dbus.mainloop.glib import threads_init


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
threads_init()
DBusGMainLoop(set_as_default=True)

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)

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

import time

import scarlett_player
# BOSSJONES DISABLE # import scarlett_speaker
# BOSSJONES DISABLE # import scarlett_forecast
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
        # NOTE USE THIS AS AN EXAMPLE ON HOW TO DO CLIENT
        # source: https://github.com/hexchat/hexchat/blob/master/src/common/dbus/example-gdbus.py
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.proxy = Gio.DBusProxy.new_sync(self.bus,
                                                Gio.DBusProxyFlags.NONE,
                                                None,
                                                'com.example.service',
                                                '/com/example/service',
                                                'com.example.service',
                                                None)
        except:
            print "Exception: %s" % sys.exec_info()[1]

        # source: https://git.gnome.org/browse/glib/tree/gio/gdbusproxy.c?h=2.46.2#n2957
        self._quit = self.proxy.call('com.example.service.Quit',
                                     None,
                                     Gio.DBusCallFlags.NO_AUTO_START,
                                     500,
                                     None,
                                     None)

        self._tasker_connected = self.proxy.call('com.example.service.emitConnectedToListener',
                                                 None,
                                                 Gio.DBusCallFlags.NO_AUTO_START,
                                                 500,
                                                 None,
                                                 None)
        # -------------------

        self._loop = GLib.MainLoop()
        bus = dbus.SessionBus()

        # DISABLED # # NOTE: This is a proxy dbus command
        # DISABLED # service = bus.get_object('com.example.service', "/com/example/service")
        # DISABLED # self._quit = service.get_dbus_method(
        # DISABLED #     'quit', 'com.example.service.Quit')
        # DISABLED # self._tasker_connected = service.get_dbus_method(
        # DISABLED #     'emitConnectedToListener',
        # DISABLED #     'com.example.service.emitConnectedToListener')

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
                GLib.timeout_add(200, wait_for_t, t)

        def player_cb(*args, **kwargs):
            logger.debug("player_cb PrettyPrinter: ")
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(args)
            msg, scarlett_sound = args
            logger.warning(" msg: {}".format(msg))
            logger.warning(" scarlett_sound: {}".format(scarlett_sound))

            # Our thread will run start_listening
            scarlett_player.ScarlettPlayer(scarlett_sound)

#### BOSSJONES DISABLED #         def command_cb(*args, **kwargs):
#### BOSSJONES DISABLED #             logger.debug("player_cb PrettyPrinter: ")
#### BOSSJONES DISABLED #             pp = pprint.PrettyPrinter(indent=4)
#### BOSSJONES DISABLED #             pp.pprint(args)
#### BOSSJONES DISABLED #             msg, scarlett_sound, command = args
#### BOSSJONES DISABLED #             logger.warning(" msg: {}".format(msg))
#### BOSSJONES DISABLED #             logger.warning(" scarlett_sound: {}".format(scarlett_sound))
#### BOSSJONES DISABLED #             logger.warning(" command: {}".format(command))
#### BOSSJONES DISABLED #
#### BOSSJONES DISABLED #             # play sound
#### BOSSJONES DISABLED #
#### BOSSJONES DISABLED #             # Our thread will run start_listening
#### BOSSJONES DISABLED #             scarlett_player.ScarlettPlayer(scarlett_sound)
#### BOSSJONES DISABLED #
#### BOSSJONES DISABLED #             if command in scarlett_constants.FORECAST_CMDS.keys():
#### BOSSJONES DISABLED #
#### BOSSJONES DISABLED #                 fio_hourly, fio_summary, fio_day = text = scarlett_forecast.ScarlettForecast(
#### BOSSJONES DISABLED #                     self.config, command).api()
#### BOSSJONES DISABLED #                 logger.info(" Lets try putting these in one sentance:")
#### BOSSJONES DISABLED #                 logger.info(" text: {}".format(text))
#### BOSSJONES DISABLED #                 logger.warning(" fio_hourly: {}".format(fio_hourly))
#### BOSSJONES DISABLED #                 logger.warning(" fio_summary: {}".format(fio_summary))
#### BOSSJONES DISABLED #                 logger.warning(" fio_day: {}".format(fio_day))
#### BOSSJONES DISABLED #                 logger.debug(" fio_hourly. fio_summary. fio_day. =  {}. {}. {}.".format(
#### BOSSJONES DISABLED #                     fio_hourly, fio_summary, fio_day))
#### BOSSJONES DISABLED #
#### BOSSJONES DISABLED #                 # if text > 1:
#### BOSSJONES DISABLED # #
#### BOSSJONES DISABLED #                 # Our thread will run start_listening
#### BOSSJONES DISABLED #                 # Lets have the threads wait before doing the next thing
#### BOSSJONES DISABLED #                 # see this: http://stackoverflow.com/questions/26172107/gobject-idle-add-thread-join-and-my-program-hangs
#### BOSSJONES DISABLED #                 #     speaker_thread = threading.Thread(target=scarlett_speaker.ScarlettSpeaker(command).run())
#### BOSSJONES DISABLED #                 #     speaker_thread.daemon = True
#### BOSSJONES DISABLED #                 #     speaker_thread.start()

        # SIGNAL: When someone says Scarlett
        # BOSSJONES DISABLED # bus.add_signal_receiver(player_cb,
        # BOSSJONES DISABLED #                         dbus_interface='com.example.service.event',
        # BOSSJONES DISABLED #                         signal_name='KeywordRecognizedSignal'
        # BOSSJONES DISABLED #                         )

        kw = self.proxy.call('com.example.service.event.KeywordRecognizedSignal',
                                     None,
                                     None,
                                     500,
                                     None,
                                     player_cb)
        # BOSSJONES DISABLED #         bus.add_signal_receiver(command_cb,
        # BOSSJONES DISABLED #                                 dbus_interface='com.example.service.event',
        # BOSSJONES DISABLED #                                 signal_name='CommandRecognizedSignal'
        # BOSSJONES DISABLED #                                 )
        # BOSSJONES DISABLED # bus.add_signal_receiver(player_cb,
        # BOSSJONES DISABLED #                         dbus_interface='com.example.service.event',
        # BOSSJONES DISABLED #                         signal_name='SttFailedSignal'
        # BOSSJONES DISABLED #                         )
        # BOSSJONES DISABLED # bus.add_signal_receiver(player_cb,
        # BOSSJONES DISABLED #                         dbus_interface='com.example.service.event',
        # BOSSJONES DISABLED #                         signal_name='ListenerCancelSignal'
        # BOSSJONES DISABLED #                         )

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
