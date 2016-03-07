#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys
import time

SCARLETT_DEBUG = None

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
from signal import signal, SIGWINCH, SIGKILL, SIGTERM

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
import threading
import traceback
from functools import wraps
import Queue
from random import randint


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


# source: https://github.com/jcollado/pygtk-webui/blob/master/demo.py
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

NUM_THREADS = 10


class ExcThread(threading.Thread):
    """
    Exception Thread Class aka Producer. Acts as the Child thread.
    Any errors that happen here will get placed into a Queue and raised for the parent thread to consume.

    A thread class that supports raising exception in the thread from another thread.
    """

    @trace
    def __init__(self, bucket, *args, **kargs):
        threading.Thread.__init__(self, *args, **kargs)
        self.bucket = bucket
        self.running = True
        self._stop = threading.Event()

    @trace
    def run(self):
        try:
            print "Child Thread Started", self
            threading.Thread.run(self)
            # raise Exception('An error occured here.')
        except Exception:
            self.bucket.put(sys.exc_info())
            raise

    @trace
    def stop(self):
        self._stop.set()

    @trace
    def stopped(self):
        return self._stop.isSet()


@trace
def main():
    """
    Parent thread and supervisor.
    """
    bucket = Queue.Queue()

    # TODO: Try calling child thread like below.
    # TODO: Allow us to pass in a target, and args.
    # TODO: Eg. target=ScarlettPlayer or target=ScarlettSpeaker
    # SOURCE: https://github.com/jhcepas/npr/blob/master/nprlib/interface.py
    # t = ExcThread(bucket=exceptions, target=func, args=[args])
    # Start child thread
    thread_obj = ExcThread(bucket)
    thread_obj.daemon = True
    thread_obj.start()

    while True:
        try:
            exc = bucket.get(block=False)
            # print "GOT FROM BUCKET QUEUE: ", exc
        except Queue.Empty:
            time.sleep(.2)
            pass
        else:
            exc_type, exc_obj, exc_trace = exc
            # deal with the exception
            # print exc_type, exc_obj
            # print exc_trace
            # deal with the exception
            # print exc_trace, exc_type, exc_obj
            raise exc_obj

        thread_obj.join(0.1)
        if thread_obj.isAlive():
            continue
        else:
            break


if __name__ == '__main__':
    main()
