# -*- coding: utf-8 -*-

# NOTE: THIS IS THE CLASS THAT WILL STORE ALL OF THE EXCEPTIONS ETC

"""Scarlett Generator Object audio utils"""

from __future__ import with_statement
from __future__ import division

import sys
import os
import random  # NOQA
import re
import unicodedata
import threading
import subprocess  # NOQA


from gettext import gettext as _
from urlparse import urlparse, urlunparse, urlsplit
urlparse, urlunparse, urlsplit
from urllib import pathname2url, url2pathname, quote_plus, unquote_plus
pathname2url, url2pathname, quote_plus, unquote_plus
from urllib2 import urlopen, build_opener
urlopen, build_opener

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
# Gst.init(None)


import generator_log  # NOQA
import contextlib
import time
import textwrap  # NOQA
import logging
from functools import wraps
import traceback
logger = logging.getLogger('scarlettlogger')

_FSCODING = "utf-8"

text_type = unicode
string_types = (str, unicode)
integer_types = (int, long)
number_types = (int, long, float)

PY2 = sys.version_info[0] == 2

########################################################################################################################
# START - SOURCE: https://github.com/quodlibet/quodlibet/blob/master/quodlibet/quodlibet/util/__init__.py
########################################################################################################################

if PY2:
    def gdecode(s):  # NOQA
        """Returns unicode for the glib text type"""

        assert isinstance(s, bytes)
        return s.decode("utf-8")
else:
    def gdecode(s):  # NOQA
        """Returns unicode for the glib text type"""

        assert isinstance(s, text_type)
        return s


class InstanceTracker(object):  # NOQA
    """A mixin for GObjects to return a list of all alive objects
    of a given type. Note that it must be used with a GObject or
    something with a connect method and destroy signal."""
    __kinds = {}

    def _register_instance(self, klass=None):
        """Register this object to be returned in the active instance list."""
        if klass is None:
            klass = type(self)
        self.__kinds.setdefault(klass, []).append(self)
        self.connect('destroy', self.__kinds[klass].remove)

    @classmethod
    def instances(klass):
        return klass.__kinds.get(klass, [])


def escape(str):
    """Escape a string in a manner suitable for XML/Pango."""
    return str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape(str):
    """Unescape a string in a manner suitable for XML/Pango."""
    return str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def parse_time(timestr, err=(ValueError, re.error)):
    """Parse a time string in hh:mm:ss, mm:ss, or ss format."""
    if timestr[0:1] == "-":
        m = -1
        timestr = timestr[1:]
    else:
        m = 1
    try:
        return m * reduce(lambda s, a: s * 60 + int(a),
                          re.split(r":|\.", timestr), 0)
    except err:
        return 0


def validate_query_date(datestr):  # NOQA
    """Validates a user provided date that can be compared using date_key().

    Returns True id the date is valid.
    """

    parts = datestr.split("-")
    if len(parts) > 3:
        return False

    if len(parts) > 2:
        try:
            v = int(parts[2])
        except ValueError:
            return False
        else:
            if not 1 <= v <= 31:
                return False

    if len(parts) > 1:
        try:
            v = int(parts[1])
        except ValueError:
            return False
        else:
            if not 1 <= v <= 12:
                return False

    try:
        int(parts[0])
    except ValueError:
        return False

    return True


def date_key(datestr):  # NOQA
    """Parse a date format y-m-d and returns an undefined integer that
    can only be used to compare dates.

    In case the date string is invalid the returned value is undefined.
    """

    # this basically does "2001-02-03" -> 20010203

    default = [0, 1, 1]
    parts = datestr.split("-")
    parts += default[len(parts):]

    value = 0
    for d, p, m in zip(default, parts, (10000, 100, 1)):
        try:
            value += int(p) * m
        except ValueError:
            # so that "2003-01-" is equal to "2003-01" ..
            value += d * m
    return value


def parse_date(datestr):  # NOQA
    """Parses yyyy-mm-dd date format and returns unix time.

    Raises ValueError in case the input couldn't be parsed.
    """

    import time

    try:
        frmt = ["%Y", "%Y-%m", "%Y-%m-%d"][datestr.count("-")]
    except IndexError:
        raise ValueError

    return time.mktime(time.strptime(datestr, frmt))


def format_rating(value, blank=True):
    """Turn a number into a sequence of rating symbols."""

    from quodlibet import config

    prefs = config.RATINGS
    steps = prefs.number
    value = max(min(value, 1.0), 0)
    ons = int(round(steps * value))
    offs = (steps - ons) if blank else 0
    return prefs.full_symbol * ons + prefs.blank_symbol * offs


def format_bitrate(value):
    return _("%d kbps") % int(value)


def format_size(size):
    """Turn an integer size value into something human-readable."""
    # TODO: Better i18n of this (eg use O/KO/MO/GO in French)
    if size >= 1024 ** 3:
        return "%.1f GB" % (float(size) / (1024 ** 3))
    elif size >= 1024 ** 2 * 100:
        return "%.0f MB" % (float(size) / (1024 ** 2))
    elif size >= 1024 ** 2 * 10:
        return "%.1f MB" % (float(size) / (1024 ** 2))
    elif size >= 1024 ** 2:
        return "%.2f MB" % (float(size) / (1024 ** 2))
    elif size >= 1024 * 10:
        return "%d KB" % int(size / 1024)
    elif size >= 1024:
        return "%.2f KB" % (float(size) / 1024)
    else:
        return "%d B" % size


def format_time(time):
    """Turn a time value in seconds into hh:mm:ss or mm:ss."""

    if time < 0:
        time = abs(time)
        prefix = "-"
    else:
        prefix = ""
    if time >= 3600:  # 1 hour
        # time, in hours:minutes:seconds
        return "%s%d:%02d:%02d" % (prefix, time // 3600,
                                   (time % 3600) // 60, time % 60)
    else:
        # time, in minutes:seconds
        return "%s%d:%02d" % (prefix, time // 60, time % 60)


def format_time_display(time):
    """Like format_time, but will use RATIO instead of a colon to separate"""

    return format_time(time).replace(":", u"\u2236")


def capitalize(str):
    """Capitalize a string, not affecting any character after the first."""
    return str[:1].upper() + str[1:]


def _split_numeric_sortkey(s, limit=10,
                           reg=re.compile(r"[0-9][0-9]*\.?[0-9]*").search,
                           join=u" ".join):
    """Separate numeric values from the string and convert to float, so
    it can be used for human sorting. Also removes all extra whitespace."""
    result = reg(s)
    if not result or not limit:
        text = join(s.split())
        return (text,) if text else tuple()
    else:
        start, end = result.span()
        return (
            join(s[:start].split()),
            float(result.group()),
            _split_numeric_sortkey(s[end:], limit - 1))


def human_sort_key(s, normalize=unicodedata.normalize):
    if not s:
        return ()
    if not isinstance(s, text_type):
        s = s.decode("utf-8")
    s = normalize("NFD", s.lower())
    return _split_numeric_sortkey(s)


def spawn(argv, stdout=False):
    """Asynchronously run a program. argv[0] is the executable name, which
    must be fully qualified or in the path. If stdout is True, return
    a file object corresponding to the child's standard output; otherwise,
    return the child's process ID.

    argv must be strictly str objects to avoid encoding confusion.
    """

    from gi.repository import GLib  # NOQA

    types = map(type, argv)
    if not (min(types) == max(types) == str):
        raise TypeError("executables and arguments must be str objects")
    logger.debug("Running %r" % " ".join(argv))
    args = GLib.spawn_async(argv=argv, flags=GLib.SpawnFlags.SEARCH_PATH,
                            standard_output=stdout)

    if stdout:
        return os.fdopen(args[2])
    else:
        return args[0]


def fver(tup):
    return ".".join(map(str, tup))


def uri_is_valid(uri):
    return bool(urlparse(uri)[0])


def make_case_insensitive(filename):
    return "".join(["[%s%s]" % (c.lower(), c.upper()) for c in filename])


class DeferredSignal(object):
    """A wrapper for connecting functions to signals.

    Some signals may fire hundreds of times, but only require processing
    once per group. This class pushes the call to the mainloop at idle
    priority and prevents multiple calls from being inserted in the
    mainloop at a time, greatly improving responsiveness in some places.

    When the target function is finally called, the arguments passed
    are the last arguments passed to DeferredSignal.

    `priority` defaults to GLib.PRIORITY_DEFAULT

    If `owner` is given, it will not call the target after the owner is
    destroyed.

    Example usage:

    def func(widget, user_arg):
        pass
    widget.connect('signal', DeferredSignal(func, owner=widget), user_arg)
    """

    def __init__(self, func, timeout=None, owner=None, priority=None):
        """timeout in milliseconds"""

        self.func = func
        self.dirty = False
        self.args = None

        if owner:
            def destroy_cb(owner):
                self.abort()
            owner.connect("destroy", destroy_cb)

        from gi.repository import GLib  # NOQA

        if priority is None:
            priority = GLib.PRIORITY_DEFAULT

        if timeout is None:
            self.do_idle_add = lambda f: GLib.idle_add(f, priority=priority)
        else:
            self.do_idle_add = lambda f: GLib.timeout_add(
                timeout, f, priority=priority)

    @property
    def __self__(self):
        return self.func.__self__

    @property
    def __code__(self):
        return self.func.__code__

    @property
    def __closure__(self):
        return self.func.__closure__

    def abort(self):
        """Abort any queued up calls.

        Can still be reused afterwards.
        """

        if self.dirty:
            from gi.repository import GLib  # NOQA
            GLib.source_remove(self._id)
            self.dirty = False
            self.args = None

    def __call__(self, *args):
        self.args = args
        if not self.dirty:
            self.dirty = True
            self._id = self.do_idle_add(self._wrap)

    def _wrap(self):
        self.func(*self.args)
        self.dirty = False
        self.args = None
        return False


def connect_obj(this, detailed_signal, handler, that, *args, **kwargs):
    """A wrapper for connect() that has the same interface as connect_object().
    Used as a temp solution to get rid of connect_object() calls which may
    be changed to match the C version more closely in the future.

    https://git.gnome.org/browse/pygobject/commit/?id=86fb12b3e9b75

    While it's not clear if switching to weak references will break anything,
    we mainly used this for adjusting the callback signature. So using
    connect() behind the scenes will keep things working as they are now.
    """

    def wrap(this, *args):
        return handler(that, *args)

    return this.connect(detailed_signal, wrap, *args, **kwargs)


def _connect_destroy(sender, func, detailed_signal, handler, *args, **kwargs):
    """Connect a bound method to a foreign object signal and disconnect
    if the object the method is bound to emits destroy (Gtk.Widget subclass).

    Also works if the handler is a nested function in a method and
    references the method's bound object.

    This solves the problem that the sender holds a strong reference
    to the bound method and the bound to object doesn't get GCed.
    """

    if hasattr(handler, "__self__"):
        obj = handler.__self__
    else:
        # XXX: get the "self" var of the enclosing scope.
        # Used for nested functions which ref the object but aren't methods.
        # In case they don't ref "self" normal connect() should be used anyway.
        index = handler.__code__.co_freevars.index("self")
        obj = handler.__closure__[index].cell_contents

    assert obj is not sender

    handler_id = func(detailed_signal, handler, *args, **kwargs)

    def disconnect_cb(*args):
        sender.disconnect(handler_id)

    obj.connect('destroy', disconnect_cb)
    return handler_id


def connect_destroy(sender, *args, **kwargs):
    return _connect_destroy(sender, sender.connect, *args, **kwargs)


def connect_after_destroy(sender, *args, **kwargs):
    return _connect_destroy(sender, sender.connect_after, *args, **kwargs)


def gi_require_versions(name, versions):
    """Like gi.require_version, but will take a list of versions.

    Returns the required version or raises ValueError.
    """

    assert versions

    import gi

    error = None
    for version in versions:
        try:
            gi.require_version(name, version)
        except ValueError as e:
            error = e
        else:
            return version
    else:
        raise error


def is_main_thread():
    """If the calling thread is the main one"""

    return threading.current_thread().name == "MainThread"


class MainRunnerError(Exception):
    pass


class MainRunnerAbortedError(MainRunnerError):
    pass


class MainRunnerTimeoutError(MainRunnerError):
    pass


class MainRunner(object):
    """Schedule a function call in the main loop from a
    worker thread and wait for the result.

    Make sure to call abort() before the main loop gets destroyed, otherwise
    the worker thread may block forever in call().
    """

    def __init__(self):
        self._source_id = None
        self._call_id = None
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._return = None
        self._error = None
        self._aborted = False

    def _run(self, func, *args, **kwargs):
        try:
            self._return = func(*args, **kwargs)
        except Exception as e:
            self._error = MainRunnerError(e)

    def _idle_run(self, call_id, call_event, func, *args, **kwargs):
        call_event.set()
        with self._lock:
            # In case a timeout happened but this got still
            # scheduled, this could be called after call() returns;
            # Compare to the current call id and do nothing if it isn't ours
            if call_id is not self._call_id:
                return False
            try:
                self._run(func, *args, **kwargs)
            finally:
                self._source_id = None
                self._cond.notify()
                return False

    def abort(self):
        """After this call returns no function will be executed anymore
        and a currently blocking call will fail with MainRunnerAbortedError.

        Can be called multiple times and can not fail.
        call() will always fail after this was called.
        """

        from gi.repository import GLib  # NOQA

        with self._lock:
            if self._aborted:
                return
            if self._source_id is not None:
                GLib.source_remove(self._source_id)
                self._source_id = None
            self._aborted = True
            self._call_id = None
            self._error = MainRunnerAbortedError("aborted")
            self._cond.notify()

    def call(self, func, *args, **kwargs):
        """Runs the function in the main loop and blocks until
        it is finshed or abort() was called. In case this is called
        from the main loop the function gets executed immediately.

        The priority kwargs defines the event source priority and will
        not be passed to func.

        In case a timeout kwarg is given the call will raise
        MainRunnerTimeoutError in case the function hasn't been scheduled
        (doesn't mean returned) until that time. timeout is a float in seconds.

        Can raise MainRunnerError in case the function raises an exception.
        Raises MainRunnerAbortedError in case the runner was aborted.
        Raises MainRunnerTimeoutError in case the timeout was reached.
        """

        from gi.repository import GLib  # NOQA

        with self._lock:
            if self._aborted:
                raise self._error
            self._error = None
            # XXX: ideally this should be GLib.MainContext.default().is_owner()
            # but that's not available in older pygobject
            if is_main_thread():
                kwargs.pop("priority", None)
                self._run(func, *args, **kwargs)
            else:
                assert self._source_id is None
                assert self._call_id is None
                timeout = kwargs.pop("timeout", None)
                call_event = threading.Event()
                self._call_id = object()
                self._source_id = GLib.idle_add(
                    self._idle_run, self._call_id, call_event,
                    func, *args, **kwargs)
                # only wait for the result if we are sure it got scheduled
                if call_event.wait(timeout):
                    self._cond.wait()
                self._call_id = None
                if self._source_id is not None:
                    GLib.source_remove(self._source_id)
                    self._source_id = None
                    raise MainRunnerTimeoutError("timeout: %r" % timeout)
            if self._error is not None:
                raise self._error
            return self._return


def re_escape(string, BAD="/.^$*+-?{,\\[]|()<>#=!:"):
    """A re.escape which also works with unicode"""

    needs_escape = lambda c: (c in BAD and "\\" + c) or c  # NOQA
    return type(string)().join(map(needs_escape, string))


# def reraise(tp, value, tb=None):
#     """Reraise an exception with a new exception type and
#     the original stack trace
#     """
#
#     if tb is None:
#         tb = sys.exc_info()[2]
#     py_reraise(tp, value, tb)


########################################################################################################################
# END - SOURCE: https://github.com/quodlibet/quodlibet/blob/master/quodlibet/quodlibet/util/__init__.py
########################################################################################################################


class _IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """

    # @trace
    def __init__(self):
        GObject.GObject.__init__(self)

    # @trace
    def emit(self, *args):
        GObject.idle_add(GObject.GObject.emit, self, *args)


# source: https://github.com/hpcgam/dicomimport/blob/1f265b1a5c9e631a536333633893ab525da87f16/doc-dcm/SAMPLEZ/nostaples/utils/scanning.py  # NOQA
def abort_on_exception(func):  # NOQA
    """
    This function decorator wraps the run() method of a thread
    so that any exceptions in that thread will be logged and
    cause the threads 'abort' signal to be emitted with the exception
    as an argument.  This way all exception handling can occur
    on the main thread.

    Note that the entire sys.exc_info() tuple is passed out, this
    allows the current traceback to be used in the other thread.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception, e:
            thread_object = args[0]
            exc_type, exc_value, exc_tb = exc_info = sys.exc_info()
            filename, line_num, func_name, text = traceback.extract_tb(exc_tb)[-1]
            logger.error('Exception Thrown from [%s] on line [%s] via function [%s]' % (filename, line_num, func_name))
            logger.error('Exception type %s: %s' % (e.__class__.__name__, e.message))
            # NOTE: ORIGINAL # thread_object.log.error('Exception type %s: %s' % (e.__class__.__name__, e.message))
            thread_object.emit('aborted', exc_info)
    return wrapper


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


def mkdir(dir_, *args):  # NOQA
    """Make a directory, including all its parent directories. This does not
    raise an exception if the directory already exists (and is a
    directory)."""

    try:
        os.makedirs(dir_, *args)
    except OSError as e:
        if e.errno != errno.EEXIST or not os.path.isdir(dir_):
            raise


def iscommand(s):  # NOQA
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
        filt = lambda base: not base.startswith(".")  # NOQA
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


def expanduser(filename):  # NOQA
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
