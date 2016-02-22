#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import sys

SCARLETT_DEBUG = 1

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
import signal

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)

from colorlog import ColoredFormatter

import logging
from gettext import gettext as _

gst = Gst
import time

import scarlett_config
import scarlett_gstutils

if __name__ == "__main__":

    cmd = 'Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands'
    loop = GLib.MainLoop()

    def _onBusError(bus, message):
        try:
            time.sleep(1)
            p = pipelines_stack[0]
            p.set_state(Gst.State.NULL)
        except:
            print 'error in _onBusError when trying to set state'
        loop.quit()
        return True

    def _on_bus_eos(bus, message):
        try:
            time.sleep(1)
            p = pipelines_stack[0]
            p.set_state(Gst.State.NULL)
        except:
            print 'error in _on_bus_eos when trying to set state'
        loop.quit()
        return True

    pipelines_stack = []
    source_stack = []

    _message = 'This is the ScarlettSpeaker'
    config = scarlett_config.Config()
    override_parse = ''
    failed = 0
    kw_found = 0
    debug = False
    create_dot = False

    #########################################################################
    espeak_pipeline = 'espeak name=source ! queue2 name=q ! autoaudiosink'
    player = Gst.parse_launch(espeak_pipeline)
    print '********************************************************'
    print 'player from espeak_pipeline: '
    pp.pprint(player)
    print '********************************************************'
    end_cond = threading.Condition(threading.Lock())

    #######################################################################
    # all writable properties(including text) make sense only at start playing;
    # to apply new values you need to stop pipe.set_state(Gst.State.NULL) pipe and
    # start it again with new properties pipe.set_state(Gst.State.PLAYING).
    # source: http://wiki.sugarlabs.org/go/Activity_Team/gst-plugins-espeak
    #######################################################################
    # Set the uri to the cmd
    source = player.get_by_name("source")
    source.props.pitch = 50
    source.props.rate = 20
    source.props.voice = "en+f3"
    source.props.text = _('{}'.format(cmd))
    text = source.props.text

    # Enable message bus to check for errors in the pipeline
    gst_bus = player.get_bus()
    gst_bus.add_signal_watch()

    # NOTE: Borrowed these lines from gnome-music
    # gst_bus.connect('message::error', _onBusError)
    # gst_bus.connect('message::eos', _on_bus_eos)

    pipelines_stack.append(player)
    source_stack.append(source)

    # Tracer()()

    pp.pprint(dir(source))

    # mainloopthread = scarlett_gstutils.MainloopThread(loop)
    # mainloopthread.start()

    # start pipeline
    player.set_state(Gst.State.PLAYING)

    GST_CLOCK_TIME_NONE = 18446744073709551615

    # wait for preroll or error
    msg=gst_bus.timed_pop_filtered(GST_CLOCK_TIME_NONE, Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR)

    if msg.type == Gst.MessageType.ASYNC_DONE:
      ret, dur = player.query_duration(Gst.Format.TIME)
      print "Duration: %u seconds" % (dur / Gst.SECOND)

      # wait for EOS or error
      msg=gst_bus.timed_pop_filtered(GST_CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR)

    if msg.type == Gst.MessageType.ERROR:
      gerror, dbg_msg = msg.parse_error()
      print "Error         : ", gerror.message
      print "Debug details : ", dbg_msg

    player.set_state(Gst.State.NULL)



    ######################################
    # import test_gdbus_speaker

    # test_gdbus_speaker.ScarlettSpeaker('Hello sir. How are you doing this afternoon? I am full lee function nall, andd red ee for your commands')
