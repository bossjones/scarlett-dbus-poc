#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Python example demonstrating when callbacks are run in a threaded environment
# John Stowers

import os
import sys
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject
GObject.threads_init()

import threading
import thread
import time
import random

import StringIO

import re
import ConfigParser
from signal import signal, SIGWINCH, SIGKILL, SIGTERM

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

from colorlog import ColoredFormatter

import logging

from gettext import gettext as _

import traceback
from functools import wraps
import Queue


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


def trace(func):
    """Tracing wrapper to log when function enter/exit happens.
    :param func: Function to wrap
    :type func: callable
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug('Start {!r}'. format(func.__name__))
        result = func(*args, **kwargs)
        logger.debug('End {!r}'. format(func.__name__))
        return result
    return wrapper


# Create a player
logger = setup_logger()


class Test(threading.Thread, GObject.GObject):
    __gsignals__ = {
        "now": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
        "idle": (GObject.SignalFlags.RUN_FIRST, None, (str, str))
    }

    def __init__(self):
        threading.Thread.__init__(self)
        GObject.GObject.__init__(self)

    def run(self):
        print "run"
        while 1:
            self.emit("now", "now", str(thread.get_ident()))
            GObject.idle_add(self.emit, "idle", "idle",
                             str(thread.get_ident()))
            time.sleep(1)


def cb(sender, how, i):
    print "%s cb %s vs thread %s" % (how, thread.get_ident(), i)


def tick():
    print "ml %s ..." % thread.get_ident()
    return True

GObject.timeout_add_seconds(1, tick)

t = Test()
t.connect("now", cb)
t.connect("idle", cb)
t.start()

Gtk.main()
