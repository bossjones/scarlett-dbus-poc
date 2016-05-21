#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys

import pprint
pp = pprint.PrettyPrinter(indent=4)

# pylint: disable=E0611
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
import threading
# pylint: enable=E0611

# GObject.threads_init()

import signal

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)
import logging
logger = logging.getLogger('scarlettlogger')

import generator_utils

from gettext import gettext as _
import contextlib
import time
import textwrap

import generator_subprocess

_pitch = 75
_speed = 175
_wavpath = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav"
_voice = "en+f3"
_text = _('{}'.format("Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands"))
_word_gap = 1
_rate = 100

_command = ["espeak", "-p%s" % _pitch,
            "-s%s" % _speed, "-g%s" % _word_gap,
            "-w", _wavpath, "-v%s" % _voice,
            ".   %s   ." % _text]

res = generator_subprocess.Subprocess(_command, name='espeak_tmp', fork=False).run()

print "Did is run successfully? {}".format(res)
