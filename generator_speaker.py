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


QUEUE_SIZE = 10
BUFFER_SIZE = 10
SENTINEL = '__GSTDEC_SENTINEL__'
PITCH_MAX = 200
RATE_MAX = 200
PITCH_DEFAULT = PITCH_MAX / 2
RATE_DEFAULT = RATE_MAX / 2

_GST_STATE_MAPPING = {
    Gst.State.PLAYING: 'playing',
    Gst.State.PAUSED: 'paused',
    Gst.State.NULL: 'stopped',
}

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

# Managing the Gobject main loop thread.

_shared_loop_thread = None
_loop_thread_lock = threading.RLock()


def get_loop_thread():
    """Get the shared main-loop thread.
    """
    global _shared_loop_thread
    with _loop_thread_lock:
        if not _shared_loop_thread:
            # Start a new thread.
            _shared_loop_thread = MainLoopThread()
            _shared_loop_thread.start()
        return _shared_loop_thread


class MainLoopThread(threading.Thread):
    """A daemon thread encapsulating a Gobject main loop.
    """

    def __init__(self):
        super(MainLoopThread, self).__init__()
        self.loop = GObject.MainLoop()
        self.daemon = True

    def run(self):
        self.loop.run()


# The decoder.


class ScarlettSpeaker(object):
    # Anything defined here belongs to the class itself

    def __init__(self, text_to_speak):
        # anythning defined here belongs to the INSTANCE of the class
        self.running = False
        self.finished = False
        self._target_state = Gst.State.NULL

        espeak_pipeline = 'espeak name=source ! decodebin name=dec ! capsfilter name=capsfilter ! audioconvert name=audioconvert ! tee name=t ! queue2 name=appsink_queue ! appsink name=appsink t. ! queue2 name=fakesink_queue ! fakesink name=fakesink t. ! queue2 name=autoaudio_queue ! audioresample name=audioresample ! autoaudiosink name=autoaudiosink'
        self.pipeline = Gst.parse_launch(espeak_pipeline)

        # Set up the Gstreamer pipeline.
        # self.pipeline = Gst.Pipeline('speaker-main-pipeline')
        # ORIG # self.ready_sem = threading.Semaphore(0)
        self.ready_sem = threading.Semaphore(0)

        # Register for bus signals.
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._message)
        bus.connect("message::error", self._message)
        bus.connect("message::state-changed", self._on_state_changed)

        # 1. Create pipeline's elements
        self.source = self.pipeline.get_by_name("source")
        self.dec = self.pipeline.get_by_name("dec")
        # self.source = Gst.ElementFactory.make("espeak", 'source')
        # self.dec = Gst.ElementFactory.make("decodebin", None)
        # self.capsfilter = Gst.ElementFactory.make('capsfilter', None)
        self.capsfilter = self.pipeline.get_by_name("capsfilter")

        # self.audioconvert = Gst.ElementFactory.make('audioconvert', None)
        # self.splitter = Gst.ElementFactory.make("tee", 'splitter')
        self.audioconvert = self.pipeline.get_by_name("audioconvert")
        self.splitter = self.pipeline.get_by_name("t")

        # self.queueA = Gst.ElementFactory.make('queue2', None)
        # self.appsink = Gst.ElementFactory.make('appsink', None)
        self.queueA = self.pipeline.get_by_name("appsink_queue")
        self.appsink = self.pipeline.get_by_name("appsink")

        # self.queueB = Gst.ElementFactory.make('queue2', None)
        # self.audioresample = Gst.ElementFactory.make('audioresample', None)
        # self.pulsesink = Gst.ElementFactory.make('pulsesink', None)
        self.queueB = self.pipeline.get_by_name("autoaudio_queue")
        self.audioresample = self.pipeline.get_by_name("audioresample")
        self.pulsesink = self.pipeline.get_by_name("autoaudiosink")

        self.queueC = self.pipeline.get_by_name("fakesink_queue")
        self.fakesink = self.pipeline.get_by_name("fakesink")

        # logger.error(self.source)
        # logger.error(self.dec)
        # logger.error(self.capsfilter)
        # logger.error(self.audioconvert)
        # logger.error(self.splitter)
        # logger.error(self.appsink)
        # logger.error(self.queueB)
        # logger.error(self.audioresample)
        # logger.error(self.pulsesink)

        if (not self.source
                or not self.dec
                or not self.capsfilter
                or not self.audioconvert
                or not self.splitter
                or not self.queueA
                or not self.appsink
                or not self.queueB
                or not self.audioresample
                or not self.pulsesink
                or not self.queueC
                or not self.fakesink):
            logger.error("ERROR: Not all elements could be created.")
            raise generator_utils.IncompleteGStreamerError()

        # 2. Set properties
        # # espeak
        # source = self.pipeline.get_by_name("source")
        # source.props.pitch = 50
        # source.props.rate = 100
        # source.props.voice = "en+f3"
        # source.props.text = _('{}'.format(cmd))
        # self.text = source.props.text

        source = self.pipeline.get_by_name("source")
        _text = _('{}'.format(text_to_speak))
        # source = self.source
        source.props.text = _text
        source.props.pitch = 50
        source.props.rate = 100
        # self.source.props('track', 2)
        source.props.voice = "en+f3"
        self.text = source.props.text

        source.set_property('text', _text)
        source.set_property('pitch', 50)
        source.set_property('rate', 100)
        source.set_property('voice', "en+f3")

        # _pitch = '50'
        # _rate = '100'
        # _uint_pitch = _pitch & 0xff
        # _uint_rate = _rate & 0xff
        # logger.error("_uint_pitch = {} ".format(_uint_pitch))
        # logger.error("_uint_rate = {} ".format(_uint_rate))

        # espeak, testing props
        # self.source.props.text = _text
        # self.source.props.pitch = 50
        # self.source.props.rate = 100

        # decodebin
        self.dec.set_property('use-buffering', True)

        # capsfilter
        self.capsfilter.set_property(
            'caps',
            Gst.Caps.from_string('audio/x-raw, format=(string)S16LE, layout=(string)interleaved, rate=(int)22050, channels=(int)1'),
        )

        # audioconvert

        # queueA
        self.queueA.set_property('max-size-bytes', 0)
        self.queueA.set_property('max-size-buffers', 0)
        self.queueA.set_property('max-size-time', 0)

        # appsink
        self.appsink.set_property(
            'caps',
            Gst.Caps.from_string('audio/x-raw, format=(string)S16LE'),
        )
        self.appsink.set_property('drop', False)
        self.appsink.set_property('max-buffers', BUFFER_SIZE)
        self.appsink.set_property('sync', False)
        self.appsink.set_property('emit-signals', True)

        # appsink callback setup
        self.appsink.connect("new-sample", self._new_sample)
        self.caps_handler = self.appsink.get_static_pad("sink").connect(
            "notify::caps", self._notify_caps
        )

        # queueB
        self.queueB.set_property('max-size-bytes', 0)
        self.queueB.set_property('max-size-buffers', 0)
        self.queueB.set_property('max-size-time', 0)

        # audioresample

        # Queue element to buy us time between the about-to-finish event and
        # the actual switch, i.e. about to switch can block for longer thanks
        # to this queue.
        # TODO: See if settings should be set to minimize latency. Previous
        # setting breaks appsrc, and settings before that broke on a few
        # systems. So leave the default to play it safe.
        # self.queueC.set_property('max-size-bytes', 0)
        # self.queueC.set_property('max-size-buffers', 0)
        self.queueC.set_property('max-size-time', 1 * Gst.MSECOND)

        # playbin.set_property('buffer-size', 5 << 20)  # 5MB
        # playbin.set_property('buffer-duration', 5 * Gst.SECOND)

        # pulsesink
        self.pulsesink.set_property('sync', False)

        # fakesink
        # NOTE: Taken from mopidy _Outputs
        # Add an always connected fakesink which respects the clock so the tee
        # doesn't fail even if we don't have any outputs.
        self.fakesink.set_property('sync', True)

        # # 3. Add all to pipeline
        # self.pipeline.add(self.dec,
        #                   self.audioconvert,
        #                   self.splitter,
        #                   self.queueA,
        #                   self.appsink,
        #                   self.queueB,
        #                   self.audioresample,
        #                   self.pulsesink)

        # # link elements
        # # ret = self.source.link(self.dec)
        # ret = self.buffer.link(self.dec)
        # ret = ret and self.audioconvert.link(self.splitter)
        # ret = ret and self.queueA.link(self.appsink)
        # ret = ret and self.queueB.link(self.audioresample)
        # ret = ret and self.audioresample.link(self.pulsesink)

        # logger.error("ret: {}".format(ret))

        # 4.a. uridecodebin has a "sometimes" pad (created after prerolling)
        self.dec.connect('pad-added', self._decode_src_created)
        self.dec.connect('no-more-pads', self._no_more_pads)
        self.dec.connect("unknown-type", self._unknown_type)

        # #######################################################################
        # # QUEUE A
        # #######################################################################
        # # link tee to queueA
        # tee_src_pad_to_appsink_bin = self.splitter.get_request_pad('src_%u')
        # logger.debug("Obtained request pad Name({}) Type({}) for audio branch.".format(
        #     self.splitter.name, self.splitter))
        # queueAsinkPad = self.queueA.get_static_pad('sink')
        # logger.debug(
        #     "Obtained sink pad for element ({}) for tee -> queueA.".format(queueAsinkPad))
        # tee_src_pad_to_appsink_bin.link(queueAsinkPad)

        # #######################################################################
        # # QUEUE B
        # #######################################################################
        # # link tee to queueB
        # tee_src_pad_to_appsink_bin = self.splitter.get_request_pad('src_%u')
        # logger.debug("Obtained request pad Name({}) Type({}) for audio branch.".format(
        #     self.splitter.name, self.splitter))
        # queueAsinkPad = self.queueB.get_static_pad('sink')
        # logger.debug(
        #     "Obtained sink pad for element ({}) for tee -> queueB.".format(queueAsinkPad))
        # tee_src_pad_to_appsink_bin.link(queueAsinkPad)

        # recursively print elements
        # self._listElements(self.pipeline)

        #######################################################################

        # Set up the queue for data and run the main thread.
        self.queue = queue.Queue(QUEUE_SIZE)
        self.thread = get_loop_thread()

        # This wil get filled with an exception if opening fails.
        self.read_exc = None
        self.dot_exc = None

        # Return as soon as the stream is ready!
        self.running = True
        self.got_caps = False
        self._buffering = False
        self.pipeline.set_state(Gst.State.PLAYING)
        self.on_debug_activate()
        self.ready_sem.acquire()

        if self.read_exc:
            # An error occurred before the stream became ready.
            self.close(True)
            raise self.read_exc

    def _on_state_changed(self, bus, msg):
        states = msg.parse_state_changed()
        # To state is PLAYING
        if msg.src.get_name() == "pipeline" and states[1] == 4:
            dotfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-player.dot"
            pngfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-player-pipeline.png"  # NOQA
            if os.access(dotfile, os.F_OK):
                os.remove(dotfile)
            if os.access(pngfile, os.F_OK):
                os.remove(pngfile)
            Gst.debug_bin_to_dot_file(msg.src,
                                      Gst.DebugGraphDetails.ALL, "generator-player")
            os.system('/usr/bin/dot' + " -Tpng -o " + pngfile + " " + dotfile)
            print("pipeline dot file created in " +
                  os.getenv("GST_DEBUG_DUMP_DOT_DIR"))

    def _listElements(self, bin, level=0):
        try:
            iterator = bin.iterate_elements()
            # print iterator
            while True:
                elem = iterator.next()
                if elem[1] is None:
                    break
                logger.debug(level * '** ' + str(elem[1]))
                # uncomment to print pads of element
                self._iteratePads(elem[1])
                # call recursively
                self._listElements(elem[1], level + 1)
        except AttributeError:
            pass

    def _iteratePads(self, element):
        try:
            iterator = element.iterate_pads()
            while True:
                pad = iterator.next()
                if pad[1] is None:
                    break
                logger.debug('pad: ' + str(pad[1]))
        except AttributeError:
            pass

    # NOTE: This function generates the dot file, checks that graphviz in installed and
    # then finally generates a png file, which it then displays
    def on_debug_activate(self):
        dotfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-speaker.dot"
        pngfile = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/generator-speaker-pipeline.png"  # NOQA
        if os.access(dotfile, os.F_OK):
            os.remove(dotfile)
        if os.access(pngfile, os.F_OK):
            os.remove(pngfile)
        Gst.debug_bin_to_dot_file(self.pipeline,
                                  Gst.DebugGraphDetails.ALL, "generator-speaker")
        os.system('/usr/bin/dot' + " -Tpng -o " + pngfile + " " + dotfile)

    # Gstreamer callbacks.

    def _notify_caps(self, pad, args):
        """The callback for the sinkpad's "notify::caps" signal.
        """
        # The sink has started to receive data, so the stream is ready.
        # This also is our opportunity to read information about the
        # stream.
        logger.debug("pad: {}".format(pad))
        logger.debug("pad name: {} parent: {}".format(
            pad.name, pad.get_parent()))
        logger.debug("args: {}".format(args))
        self.got_caps = True
        info = pad.get_current_caps().get_structure(0)
        # logger.error("pprint info:")
        # pp.pprint(info)

        # Stream attributes.
        self.channels = info.get_int('channels')[1]
        self.samplerate = info.get_int('rate')[1]
        self.width = info.get_int('width')[1]

        # espeak has num-buffers

        logger.error("pad.get_peer: {}".format(pad.get_peer()))
        logger.error("pad.get_peer.name: {}".format(pad.get_peer().name))
        logger.error("pad.get_peer.get_parent: {}".format(pad.get_peer().get_parent()))

        # Query duration.
        success, length = pad.get_peer().query_duration(Gst.Format.TIME)
        logger.debug("success: {}".format(success))
        logger.debug("length: {}".format(length))

        # self.caps_handler = self.appsink.get_static_pad("sink").connect(
        #     "notify::caps", self._notify_caps
        # )

        _espeak_src_pad = self.source.get_static_pad('src')
        _espeak_duration = _espeak_src_pad.query_duration(Gst.Format.TIME)
        _espeak_get_num_buffers = self.source.get_property('num-buffers')
        _espeak_get_blocksize = self.source.get_property('blocksize')
        _espeak_get_typefind = self.source.get_property('typefind')
        _espeak_get_pitch = self.source.get_property('pitch')
        _espeak_get_rate = self.source.get_property('rate')
        _espeak_get_voice = self.source.get_property('voice')
        _espeak_get_text = self.source.get_property('text')

        # logger.error('_espeak_src_pad:')
        # pp.pprint(dir(_espeak_src_pad))
        #
        # logger.error('self.source:')
        # pp.pprint(dir(self.source))

        logger.error(textwrap.dedent("""
        _espeak_src_pad = {}
        _espeak_duration = {}
        _espeak_get_num_buffers = {}
        _espeak_get_blocksize = {}
        _espeak_get_typefind = {}
        _espeak_get_pitch = {}
        _espeak_get_rate = {}
        _espeak_get_voice = {}
        _espeak_get_text = {}
        """).format(_espeak_src_pad,
                    _espeak_duration,
                    _espeak_get_num_buffers,
                    _espeak_get_blocksize,
                    _espeak_get_typefind,
                    _espeak_get_pitch,
                    _espeak_get_rate,
                    _espeak_get_voice,
                    _espeak_get_text))

        logger.error("espeak duration: {}".format(_espeak_duration))

        # define SYNC_BUFFER_SIZE_MS 200
        # define BYTES_PER_SAMPLE 2
        # define SPIN_QUEUE_SIZE 2
        # define SPIN_FRAME_SIZE 255
        # espeak_sample_rate = espeak_Initialize (AUDIO_OUTPUT_SYNCHRONOUS,
        #         SYNC_BUFFER_SIZE_MS, NULL, 0);
        # espeak_buffer_size =
        #         (SYNC_BUFFER_SIZE_MS * espeak_sample_rate) /
        #         1000 / BYTES_PER_SAMPLE;
        if success:
            self.duration = length / 1000000000
            logger.debug("FILE DURATION: {}".format(self.duration))
        else:
            self.read_exc = generator_utils.MetadataMissingError('duration not available')

        # Allow constructor to complete.
        self.ready_sem.release()

    _got_a_pad = False

    def _decode_src_created(self, element, pad):
        """The callback for GstElement's "pad-added" signal.
        """
        # Decoded data is ready. Connect up the decoder, finally.
        name = pad.query_caps(None).to_string()
        logger.debug("pad: {}".format(pad))
        logger.debug("Parent:{} of Pad:{} ".format(
            pad.get_parent(), pad.name))
        if name.startswith('audio/x-raw'):
            logger.error("inside if name.startswith('audio/x-raw')")
            logger.error("If we are inside here, we are recieving data, so we can set _got_a_pad to True")
            nextpad = self.audioconvert.get_static_pad('sink')
            self._got_a_pad = True
            # NOTE: For this speaker example, we don't care about linking, since we have to use gst-launch
            if not nextpad.is_linked():
                logger.error("inside if not nextpad.is_linked()")
                self._got_a_pad = True
                pad.link(nextpad)

    def _no_more_pads(self, element):
        """The callback for GstElement's "no-more-pads" signal.
        """
        # Sent when the pads are done adding (i.e., there are no more
        # streams in the file). If we haven't gotten at least one
        # decodable stream, raise an exception.
        if not self._got_a_pad:
            logger.error(
                "If we haven't gotten at least one decodable stream, raise an exception.")
            self.read_exc = generator_utils.NoStreamError()
            self.ready_sem.release()  # No effect if we've already started.

    def _new_sample(self, sink):
        """The callback for appsink's "new-sample" signal.
        """
        if self.running:
            # FIXME: logger.debug("sink: {}".format(sink))
            # FIXME: logger.debug("sink name: {} parent: {}".format(sink.name, sink.get_parent()))
            # New data is available from the pipeline! Dump it into our
            # queue (or possibly block if we're full).
            buf = sink.emit('pull-sample').get_buffer()
            self.queue.put(buf.extract_dup(0, buf.get_size()))
        return Gst.FlowReturn.OK

    def _unknown_type(self, uridecodebin, decodebin, caps):
        """The callback for decodebin's "unknown-type" signal.
        """
        # This is called *before* the stream becomes ready when the
        # file can't be read.
        streaminfo = caps.to_string()
        if not streaminfo.startswith('audio/'):
            # Ignore non-audio (e.g., video) decode errors.
            return
        logger.error("Ignore non-audio (e.g., video) decode errors.")
        logger.error("streaminfo: {}".format(streaminfo))
        self.read_exc = generator_utils.UnknownTypeError(streaminfo)
        self.ready_sem.release()

    def _message(self, bus, message):
        """The callback for GstBus's "message" signal (for two kinds of
        messages).
        """
        if not self.finished:
            # NOTE: Took this from mopidy
            if message.type == Gst.MessageType.STATE_CHANGED:
                if message.src != self._element:
                    return
                old_state, new_state, pending_state = message.parse_state_changed()
                self.on_playbin_state_changed(old_state, new_state, pending_state)
            elif message.type == Gst.MessageType.BUFFERING:
                self.on_buffering(message.parse_buffering(), message.get_structure())
            elif message.type == Gst.MessageType.EOS:
                # The file is done. Tell the consumer thread.
                logger.info("The file is done. Tell the consumer thread.")
                self.queue.put(SENTINEL)
                if not self.got_caps:
                    logger.error(
                        "If the stream ends before _notify_caps was called, this is an invalid file.")
                    # If the stream ends before _notify_caps was called, this
                    # is an invalid file.
                    self.read_exc = generator_utils.NoStreamError()
                    self.ready_sem.release()

            elif message.type == Gst.MessageType.ERROR:
                gerror, debug = message.parse_error()
                if 'not-linked' in debug:
                    logger.error('not-linked')
                    self.read_exc = generator_utils.NoStreamError()
                elif 'No such file' in debug:
                    self.read_exc = IOError('resource not found')
                else:
                    self.read_exc = generator_utils.FileReadError(debug)
                self.ready_sem.release()
            elif message.type == Gst.MessageType.WARNING:
                error, debug = message.parse_warning()
                self.on_warning(error, debug)
            elif message.type == Gst.MessageType.ASYNC_DONE:
                self.on_async_done()

    def on_playbin_state_changed(self, old_state, new_state, pending_state):
        logger.debug(
            'Got STATE_CHANGED bus message: old=%s new=%s pending=%s',
            old_state.value_name, new_state.value_name,
            pending_state.value_name)

        if new_state == Gst.State.READY and pending_state == Gst.State.NULL:
            # XXX: We're not called on the last state change when going down to
            # NULL, so we rewrite the second to last call to get the expected
            # behavior.
            new_state = Gst.State.NULL
            pending_state = Gst.State.VOID_PENDING

        if pending_state != Gst.State.VOID_PENDING:
            return  # Ignore intermediate state changes

        if new_state == Gst.State.READY:
            return  # Ignore READY state as it's GStreamer specific

        # new_state = _GST_STATE_MAPPING[new_state]
        # old_state, self._audio.state = self._audio.state, new_state
        #
        # target_state = _GST_STATE_MAPPING.get(self._audio._target_state)
        # if target_state is None:
        #     # XXX: Workaround for #1430, to be fixed properly by #1222.
        #     logger.debug('Race condition happened. See #1222 and #1430.')
        #     return
        # if target_state == new_state:
        #     target_state = None
        #
        # logger.debug('Audio event: state_changed(old_state=%s, new_state=%s, '
        #              'target_state=%s)', old_state, new_state, target_state)
        # AudioListener.send('state_changed', old_state=old_state,
        #                    new_state=new_state, target_state=target_state)
        # if new_state == PlaybackState.STOPPED:
        #     logger.debug('Audio event: stream_changed(uri=None)')
        #     AudioListener.send('stream_changed', uri=None)
        #
        # if 'GST_DEBUG_DUMP_DOT_DIR' in os.environ:
        #     Gst.debug_bin_to_dot_file(
        #         self._audio._playbin, Gst.DebugGraphDetails.ALL, 'mopidy')

    def on_buffering(self, percent, structure=None):
        if structure is not None and structure.has_field('buffering-mode'):
            buffering_mode = structure.get_enum(
                'buffering-mode', Gst.BufferingMode)
            if buffering_mode == Gst.BufferingMode.LIVE:
                return  # Live sources stall in paused.

        level = logging.getLevelName('TRACE')
        if percent < 10 and not self._buffering:
            self.pipeline.set_state(Gst.State.PAUSED)
            self._buffering = True
            level = logging.DEBUG
        if percent == 100:
            self._buffering = False
            if self._target_state == Gst.State.PLAYING:
                self.pipeline.set_state(Gst.State.PLAYING)
            level = logging.DEBUG

        logger.log(
            level, 'Got BUFFERING bus message: percent=%d%%', percent)

    def on_warning(self, error, debug):
        error_msg = str(error).decode('utf-8')
        debug_msg = debug.decode('utf-8')
        logger.warning('GStreamer warning: %s', error_msg)
        logger.debug(
            'Got WARNING bus message: error=%r debug=%r', error_msg, debug_msg)

    def on_async_done(self):
        logger.debug('Got ASYNC_DONE bus message.')

    # Iteration.

    def next(self):
        # Wait for data from the Gstreamer callbacks.
        val = self.queue.get()
        if val == SENTINEL:
            # End of stream.
            raise StopIteration
        return val

    # For Python 3 compatibility.
    __next__ = next

    def __iter__(self):
        return self

    # Cleanup.
    def close(self, force=False):
        """Close the file and clean up associated resources.

        Calling `close()` a second time has no effect.
        """
        if self.running or force:
            self.running = False
            self.finished = True

            # Unregister for signals, which we registered for above with
            # `add_signal_watch`. (Without this, GStreamer leaks file
            # descriptors.)
            self.pipeline.get_bus().remove_signal_watch()

            # Stop reading the file.
            # self.source.set_property("uri", None)
            self.source.set_property('text', None)

            # Block spurious signals.
            self.appsink.get_static_pad("sink").disconnect(self._notify_caps)

            # Make space in the output queue to let the decoder thread
            # finish. (Otherwise, the thread blocks on its enqueue and
            # the interpreter hangs.)
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass

            # Halt the pipeline (closing file).
            self.pipeline.set_state(Gst.State.NULL)

            # Delete the pipeline object. This seems to be necessary on Python
            # 2, but not Python 3 for some reason: on 3.5, at least, the
            # pipeline gets dereferenced automatically.
            del self.pipeline

    def __del__(self):
        self.close()

    # Context manager.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Smoke test.
if __name__ == '__main__':
    tts_list = [
        'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands']
    # ORIG # for path in sys.argv[1:]:
    for scarlett_text in tts_list:
        with time_logger('Scarlett Speaks'):
            ScarlettSpeaker(scarlett_text)
