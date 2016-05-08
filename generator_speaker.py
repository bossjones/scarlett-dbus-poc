#!/usr/bin/env python
# -*- coding: utf-8 -*-

# PIPELINE TO BUILD
# GST_DEBUG=2,identity*:5,espeak*:5,queue*:5,autoaudiosink*:5,decodebin*:5,pulse*:5,audioconvert*:5,audioresample*:5 \
# gst-launch-1.0 espeak name=source \
#                       pitch=50 \
#                       rate=20 \
#                       track=2 \
#                       voice="en+f3" \
#                       text="Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands" ! \
#                decodebin use-buffering=true ! \
#                capsfilter caps='audio/x-raw, format=(string)S16LE, layout=(string)interleaved, rate=(int)22050, channels=(int)1' ! \
#                audioconvert ! \
#                tee name=t ! \
#                queue2 name=appsink_queue \
#                       max-size-bytes=0 \
#                       max-size-buffers=0 \
#                       max-size-time=0 ! \
#                appsink caps='audio/x-raw, format=(string)S16LE, layout=(string)interleaved, rate=(int)22050, channels=(int)1' \
#                        drop=false max-buffers=10 sync=true \
#                        emit-signals=true t. ! \
#                queue2 name=autoaudio_queue \
#                       max-size-bytes=0 \
#                       max-size-buffers=0 \
#                       max-size-time=0 ! \
#                audioresample ! \
#                autoaudiosink sync=true

# NOTE: THIS IS THE CLASS THAT WILL BE REPLACING scarlett_speaker.py eventually.
# It is cleaner, more object oriented, and will allows us to run proper tests.
# Also threading.RLock() and threading.Semaphore() works correctly.

#
# There are a LOT of threads going on here, all of them managed by Gstreamer.
# If pyglet ever needs to run under a Python that doesn't have a GIL, some
# locks will need to be introduced to prevent concurrency catastrophes.
#
# At the moment, no locks are used because we assume only one thread is
# executing Python code at a time.  Some semaphores are used to block and wake
# up the main thread when needed, these are all instances of
# threading.Semaphore.  Note that these don't represent any kind of
# thread-safety.

from __future__ import with_statement
from __future__ import division

import sys
import os

os.environ[
    "GST_DEBUG_DUMP_DOT_DIR"] = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug"
os.putenv('GST_DEBUG_DUMP_DIR_DIR',
          '/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug')

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GObject
from gi.repository import Gst
from gi.repository import GLib
from gi.repository import Gio
import threading


GObject.threads_init()
Gst.init(None)

Gst.debug_set_active(True)
Gst.debug_set_default_threshold(3)
gst = Gst


import argparse
import pprint
pp = pprint.PrettyPrinter(indent=4)

try:
    import queue
except ImportError:
    import Queue as queue

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

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


@contextlib.contextmanager
def time_logger(name, level=logging.DEBUG):
    start = time.time()
    yield
    logger.log(level, '%s took %dms', name, (time.time() - start) * 1000)

# The decoder.

import generator_subprocess
import generator_player


class ScarlettSpeaker(object):
    # Anything defined here belongs to the class itself

    def __init__(self, text_to_speak="", wavpath=""):
        # anything defined here belongs to the INSTANCE of the class
        self._wavefile = []
        self._pitch = 75
        self._speed = 175
        self._wavpath = wavpath
        self._wavefile.append(self._wavpath)
        self._voice = "en+f3"
        self._text = _('{}'.format(text_to_speak))
        self._word_gap = 1
        self._command = ["espeak", "-p%s" % self._pitch,
                         "-s%s" % self._speed, "-g%s" % self._word_gap,
                         "-w", self._wavpath, "-v%s" % self._voice,
                         ".   %s   ." % self._text]

        # Write espeak data
        with time_logger('Espeak Subprocess To File'):
             self.running = True
             self.finished = False
             self.res = generator_subprocess.Subprocess(self._command, name='speaker_tmp', fork=False).run()
             generator_subprocess.check_pid(int(self.res))
             print "Did is run successfully? {}".format(self.res)

        # Have Gstreamer play it
        for path in self._wavefile:
            path = os.path.abspath(os.path.expanduser(path))
            with generator_player.ScarlettPlayer(path) as f:
                print(f.channels)
                print(f.samplerate)
                print(f.duration)
                for s in f:
                    pass

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True


    def __del__(self):
        self.close()


    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

# Smoke test.
if __name__ == '__main__':
    tts_list = [
        'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    for scarlett_text in tts_list:
        with time_logger('Scarlett Speaks'):
            ScarlettSpeaker(text_to_speak=scarlett_text, wavpath="/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav")
