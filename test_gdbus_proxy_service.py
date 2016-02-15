#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import os
import sys
import time
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

from pydbus import SessionBus

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


logger = setup_logger()

# bus = SessionBus()
#
# ss = bus.get("org.scarlett")
#
# logger.debug("ss PrettyPrinter: ")
# pp = pprint.PrettyPrinter(indent=4)
# pp.pprint(ss)


def player_cb(*args, **kwargs):
    logger.debug("player_cb PrettyPrinter: ")
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(args)
    msg, scarlett_sound = args
    logger.warning(" msg: {}".format(msg))
    logger.warning(" scarlett_sound: {}".format(scarlett_sound))


# with SessionBus() as bus:
bus = SessionBus()
# bus.watch_name("org.scarlett.Listiner1.emitListenerReadySignal", 0, player_cb)
# bus.watch_name("org.scarlett.Listiner1.emitSttFailedSignal", 0, player_cb)
ss = bus.get("org.scarlett")


logger.debug("ss PrettyPrinter: ")
pp = pprint.PrettyPrinter(indent=4)
pp.pprint(ss)

# bus.subscribe(signal="ListenerReadySignal",
#               signal_fired=player_cb)


def sigint_handler(*args):
    """Exit on Ctrl+C"""

    # Unregister handler, next Ctrl-C will kill app
    # TOD: figure out if this is really needed or not
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    GObject.MainLoop().guit()

signal.signal(signal.SIGINT, sigint_handler)

try:

    GLib.MainLoop().run()

finally:

    print 'Proxy text finished'



# bus.add_signal_receiver(command_cb,
# dbus_interface='com.example.service.event',
# signal_name='CommandRecognizedSignal'
# )
#
# 	def subscribe(self, sender=None, iface=None, signal=None, object=None, arg0=None, flags=0, signal_fired=None):
# 		"""Subscribes to matching signals.
#
# 		Subscribes to signals on connection and invokes signal_fired callback
# 		whenever the signal is received.
#
# 		To receive signal_fired callback, you need GLib main loop.
# 		You can execute it with GObject.MainLoop().run().
#
# 		Parameters
# 		----------
# 		sender : string, optional
# 			Sender name to match on (unique or well-known name) or None to listen from all senders.
# 		iface : string, optional
# 			Interface name to match on or None to match on all interfaces.
# 		signal : string, optional
# 			Signal name to match on or None to match on all signals.
# 		object : string, optional
# 			Object path to match on or None to match on all object paths.
# 		arg0 : string, optional
# 			Contents of first string argument to match on or None to match on all kinds of arguments.
# 		flags : SubscriptionFlags, optional
# 		signal_fired : callable, optional
# 			Invoked when there is a signal matching the requested data.
# 			Parameters: sender, object, iface, signal, params
#
# 		Returns
# 		-------
# 		Subscription
# 			An object you can use as a context manager to unsubscribe from the signal later.
#
# 		See Also
# 		--------
# 		See https://developer.gnome.org/gio/2.44/GDBusConnection.html#g-dbus-connection-signal-subscribe
# 		for more information.
# 		"""
# 		callback = (lambda con, sender, object, iface, signal, params: signal_fired(sender, object, iface, signal, params.unpack())) if signal_fired is not None else lambda *args: None
# 		return Subscription(self.con, sender, iface, signal, object, arg0, flags, callback)
#
#
#
# import sys
#
# try:
# 	if len(sys.argv) < 2:
# 		for unit in manager.ListUnits()[0]:
# 			print(unit)
# 	else:
# 		if sys.argv[1] == "--help":
# 			help(manager)
# 		else:
# 			command = sys.argv[1]
# 			command = "".join(x.capitalize() for x in command.split("-"))
# 			result = getattr(manager, command)(*sys.argv[2:])
#
# 			for var in result:
# 				if type(var) == list:
# 					for line in var:
# 						print(line)
# 				else:
# 					print(var)
# except Exception as e:
# 	print(e)
#
# """
# Examples:
#
# python -m pydbus.examples.systemctl
# sudo python -m pydbus.examples.systemctl start-unit cups.service replace
# """
