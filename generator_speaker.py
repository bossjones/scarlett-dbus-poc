#!/usr/bin/env python  # NOQA
# -*- coding: utf-8 -*-

"""Scarlett Speaker Module."""

# NOTE: THIS IS THE CLASS THAT WILL BE REPLACING scarlett_speaker.py eventually.
# It is cleaner, more object oriented, and will allows us to run proper tests.
# Also threading.RLock() and threading.Semaphore() works correctly.

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

from IPython.core.debugger import Tracer  # NOQA
from IPython.core import ultratb

from gettext import gettext as _

import generator_utils
from generator_utils import trace, abort_on_exception, _IdleObject
import generator_subprocess
import generator_player

import logging
logger = logging.getLogger('scarlettlogger')

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)


class ScarlettSpeaker(object):
    """Scarlett Speaker Class."""

    def __init__(self, text_to_speak="", wavpath="", skip_player=False):
        """ScarlettSpeaker object. Anything defined here belongs to the INSTANCE of the class."""
        self._wavefile = []
        self._pitch = 75
        self._speed = 175
        self._wavpath = wavpath
        self._wavefile.append(self._wavpath)
        self._voice = "en+f3"
        self._text = _(f'{text_to_speak}')
        self._word_gap = 1
        self._command = [
            "espeak",
            f"-p{self._pitch}",
            f"-s{self._speed}",
            f"-g{self._word_gap}",
            "-w",
            self._wavpath,
            f"-v{self._voice}",
            f".   {self._text}   .",
        ]

        self.path = None

        # Write espeak data
        with generator_utils.time_logger('Espeak Subprocess To File'):
            self.running = True
            self.finished = False
            self.res = generator_subprocess.Subprocess(
                self._command, name='speaker_tmp', fork=False).run()
            generator_subprocess.check_pid(int(self.res))
            print "Did is run successfully? {}".format(self.res)

        # Have Gstreamer play it
        if skip_player != True:
            for path in self._wavefile:
                path = os.path.abspath(os.path.expanduser(path))
                with generator_player.ScarlettPlayer(path) as f:
                    print(f.channels)
                    print(f.samplerate)
                    print(f.duration)

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True

    def __del__(self):
        """Garbage Collection, delete Speaker after using it."""
        self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """If something goes wrong, close class, then return exceptions."""
        self.close()
        return False

# Smoke test.
if __name__ == '__main__':
    tts_list = [
        'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    for scarlett_text in tts_list:
        with generator_utils.time_logger('Scarlett Speaks'):
            ScarlettSpeaker(text_to_speak=scarlett_text,
                            wavpath="/home/pi/dev/bossjones-github/scarlett-dbus-poc/espeak_tmp.wav")
