#!/usr/bin/env python   # NOQA
# -*- coding: utf-8 -*-

# NOTE: THIS IS THE CLASS THAT WILL STORE ALL OF THE EXCEPTIONS ETC

"""Scarlett Generator Object audio utils"""

from __future__ import with_statement
from __future__ import division

import sys
import os
import errno
from os import environ as environ
import pprint
pp = pprint.PrettyPrinter(indent=4)

from IPython.core.debugger import Tracer  # NOQA
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, GObject, Gst  # NOQA

import generator_log  # NOQA
import contextlib
import time
import textwrap  # NOQA
import logging
from functools import wraps
logger = logging.getLogger('scarlettlogger')


_FSCODING = "utf-8"

text_type = unicode
string_types = (str, unicode)
integer_types = (int, long)
number_types = (int, long, float)


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


@contextlib.contextmanager
def time_logger(name, level=logging.DEBUG):
    """Time logger context manager. Shows how long it takes to run a particular method"""
    start = time.time()
    yield
    logger.log(level, '%s took %dms', name, (time.time() - start) * 1000)


def mkdir(dir_, *args):
    """Make a directory, including all its parent directories. This does not
    raise an exception if the directory already exists (and is a
    directory)."""

    try:
        os.makedirs(dir_, *args)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(dir_):
            raise


def iscommand(s):
    """True if an executable file `s` exists in the user's path, or is a
    fully qualified and existing executable file."""

    if s == "" or os.path.sep in s:
        return os.path.isfile(s) and os.access(s, os.X_OK)
    else:
        s = s.split()[0]
        path = environ.get('PATH', '') or os.defpath
        for p in path.split(os.path.pathsep):
            p2 = os.path.join(p, s)
            if os.path.isfile(p2) and os.access(p2, os.X_OK):
                return True
        else:
            return False


def is_fsnative(path):
    """Check if file system native"""
    return isinstance(path, bytes)


def fsnative(path=u""):
    """File system native"""
    assert isinstance(path, text_type)
    return path.encode(_FSCODING, 'replace')


def glib2fsnative(path):
    """Convert glib to native filesystem format"""
    assert isinstance(path, bytes)
    return path


def fsnative2glib(path):
    """Convert file system to native glib format"""
    assert isinstance(path, bytes)
    return path

fsnative2bytes = fsnative2glib

bytes2fsnative = glib2fsnative


def listdir(path, hidden=False):
    """List files in a directory, sorted, fully-qualified.

    If hidden is false, Unix-style hidden files are not returned.
    """

    assert is_fsnative(path)

    if hidden:
        filt = None
    else:
        filt = lambda base: not base.startswith(".")
    if path.endswith(os.sep):
        join = "".join
    else:
        join = os.sep.join
    return [join([path, basename])
            for basename in sorted(os.listdir(path))
            if filt(basename)]


def mtime(filename):
    """Return the mtime of a file, or 0 if an error occurs."""
    try:
        return os.path.getmtime(filename)
    except OSError:
        return 0


def filesize(filename):
    """Return the size of a file, or 0 if an error occurs."""
    try:
        return os.path.getsize(filename)
    except OSError:
        return 0


def expanduser(filename):
    """convience function to have expanduser return wide character paths
    """
    return os.path.expanduser(filename)


def unexpand(filename, HOME=expanduser("~")):
    """Replace the user's home directory with ~/, if it appears at the
    start of the path name."""
    sub = (os.name == "nt" and "%USERPROFILE%") or "~"
    if filename == HOME:
        return sub
    elif filename.startswith(HOME + os.path.sep):
        filename = filename.replace(HOME, sub, 1)
    return filename


def get_home_dir():
    """Returns the root directory of the user, /home/user"""
    return expanduser("~")


def calculate_duration(num_samples, sample_rate):
    """Determine duration of samples using GStreamer helper for precise
    math."""
    if _gst_available():
        return Gst.util_uint64_scale(num_samples, Gst.SECOND, sample_rate)


def millisecond_to_clocktime(value):
    """Convert a millisecond time to internal GStreamer time."""
    if _gst_available():
        return value * Gst.MSECOND


def clocktime_to_millisecond(value):
    """Convert an internal GStreamer time to millisecond time."""
    if _gst_available():
        return value // Gst.MSECOND


class DecodeError(Exception):
    """The base exception class for all decoding errors raised by this
    package.
    """


class NoBackendError(DecodeError):
    """The file could not be decoded by any backend. Either no backends
    are available or each available backend failed to decode the file.
    """


class GStreamerError(DecodeError):
    """Something went terribly wrong with Gstreamer"""
    pass


class UnknownTypeError(GStreamerError):
    """Raised when Gstreamer can't decode the given file type."""

    def __init__(self, streaminfo):
        super(UnknownTypeError, self).__init__(
            "can't decode stream: " + streaminfo
        )
        self.streaminfo = streaminfo


class FileReadError(GStreamerError):
    """Raised when the file can't be read at all."""
    pass


class NoStreamError(GStreamerError):
    """Raised when the file was read successfully but no audio streams
    were found.
    """

    def __init__(self):
        super(NoStreamError, self).__init__('no audio streams found')


class MetadataMissingError(GStreamerError):
    """Raised when GStreamer fails to report stream metadata (duration,
    channels, or sample rate).
    """
    pass


class IncompleteGStreamerError(GStreamerError):
    """Raised when necessary components of GStreamer (namely, the
    principal plugin packages) are missing.
    """

    def __init__(self):
        super(IncompleteGStreamerError, self).__init__(
            'missing GStreamer base plugins'
        )


def _gst_available():
    """Determine whether Gstreamer and the Python GObject bindings are
    installed.
    """
    try:
        import gi
    except ImportError:
        return False

    try:
        gi.require_version('Gst', '1.0')
    except (ValueError, AttributeError):
        return False

    try:
        from gi.repository import Gst  # noqa
        # from gi.repository import GLib, GObject, Gst # noqa
    except ImportError:
        return False

    return True


def audio_open(path):
    """Open an audio file using a library that is available on this
    system.
    """
    # GStreamer.
    if _gst_available():
        from . import generator_player
        try:
            return generator_player.ScarlettPlayer(path)
            # return gstdec.ScarlettPlayer(path)
        except DecodeError:
            pass

    # All backends failed!
    raise NoBackendError()
