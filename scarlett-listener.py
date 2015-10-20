#!/usr/bin/env python

import dbus
import dbus.service
import dbus.mainloop.glib
from dbus.mainloop.glib import threads_init
import gobject
gobject.threads_init()
threads_init()

import pygst
pygst.require('0.10')
import gst

import StringIO
import os
import sys
import re
# import warnings
import ConfigParser

from colorama import init, Fore, Back, Style

from IPython.core.debugger import Tracer
from IPython.core import ultratb
sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux', call_pdb=True, ostream=sys.__stdout__)

from colorlog import ColoredFormatter

import logging

def setup_logger():
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "(%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s %(message_log_color)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red',
        },
        secondary_log_colors={
            'message': {
                'ERROR':    'red',
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


# dbus.mainloop.glib.threads_init()
# import threading

# If running in Google App Engine there is no "user" and
# os.path.expanduser() will fail. Attempt to detect this case and use a
# no-op expanduser function in this case.
try:
    os.path.expanduser('~')
    expanduser = os.path.expanduser
except (AttributeError, ImportError):
    # This is probably running on App Engine.
    expanduser = (lambda x: x)

# By default we use two locations for the scarlett configurations,
# /etc/scarlett.cfg and ~/.scarlett (which works on Windows and Unix).
ScarlettConfigPath = '/etc/scarlett.cfg'
ScarlettConfigLocations = [ScarlettConfigPath]
UserConfigPath = os.path.join(expanduser('~'), '.scarlett')
ScarlettConfigLocations.append(UserConfigPath)

# If there's a SCARLETT_CONFIG variable set, we load ONLY
# that variable
if 'SCARLETT_CONFIG' in os.environ:
    ScarlettConfigLocations = [expanduser(os.environ['SCARLETT_CONFIG'])]

# If there's a SCARLETT_PATH variable set, we use anything there
# as the current configuration locations, split with colons
elif 'SCARLETT_PATH' in os.environ:
    ScarlettConfigLocations = []
    for path in os.environ['SCARLETT_PATH'].split(":"):
        ScarlettConfigLocations.append(expanduser(path))


class Config(ConfigParser.SafeConfigParser):

    def __init__(self, path=None, fp=None, do_load=True):
        # We don't use ``super`` here, because ``ConfigParser`` still uses
        # old-style classes.
        ConfigParser.SafeConfigParser.__init__(
            self, {
                'working_dir': '/mnt/scarlett', 'debug': '0'})
        if do_load:
            if path:
                self.load_from_path(path)
            elif fp:
                self.readfp(fp)
            else:
                self.read(ScarlettConfigLocations)

    def load_from_path(self, path):
        file = open(path)
        for line in file.readlines():
            match = re.match("^#import[\s\t]*([^\s^\t]*)[\s\t]*$", line)
            if match:
                extended_file = match.group(1)
                (dir, file) = os.path.split(path)
                self.load_from_path(os.path.join(dir, extended_file))
        self.read(path)

    def save_option(self, path, section, option, value):
        """
        Write the specified Section.Option to the config file specified by path.
        Replace any previous value.  If the path doesn't exist, create it.
        Also add the option the the in-memory config.
        """
        config = ConfigParser.SafeConfigParser()
        config.read(path)
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
        fp = open(path, 'w')
        config.write(fp)
        fp.close()
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, value)

    def save_user_option(self, section, option, value):
        self.save_option(UserConfigPath, section, option, value)

    def save_system_option(self, section, option, value):
        self.save_option(ScarlettConfigPath, section, option, value)

    def get_user(self, name, default=None):
        try:
            val = self.get('User', name)
        except:
            val = default
        return val

    def getint_user(self, name, default=0):
        try:
            val = self.getint('User', name)
        except:
            val = default
        return val

    def get_value(self, section, name, default=None):
        return self.get(section, name, default)

    def get(self, section, name, default=None):
        try:
            val = ConfigParser.SafeConfigParser.get(self, section, name)
        except:
            val = default
        return val

    def getint(self, section, name, default=0):
        try:
            val = ConfigParser.SafeConfigParser.getint(self, section, name)
        except:
            val = int(default)
        return val

    def getfloat(self, section, name, default=0.0):
        try:
            val = ConfigParser.SafeConfigParser.getfloat(self, section, name)
        except:
            val = float(default)
        return val

    def getbool(self, section, name, default=False):
        if self.has_option(section, name):
            val = self.get(section, name)
            if val.lower() == 'true':
                val = True
            else:
                val = False
        else:
            val = default
        return val

    def setbool(self, section, name, value):
        if value:
            self.set(section, name, 'true')
        else:
            self.set(section, name, 'false')

    def dump(self):
        s = StringIO.StringIO()
        self.write(s)
        print s.getvalue()


class ScarlettListener(dbus.service.Object):

    def __init__(self, message):
        self._message = message
        self.config = Config()
        self.override_parse = ''
        self.failed = 0
        self.kw_found = 0

    def ready(self):
        self.ps_hmm = self.get_hmm_full_path()
        self.ps_dict = self.get_dict_full_path()
        self.ps_lm = self.get_lm_full_path()
        self.ps_device = self.config.get('audio', 'usb_input_device')
        self.speech_system = self.config.get('speech', 'system')
        self.parse_launch_array = self._get_pocketsphinx_definition(
            self.override_parse)
        self.pipeline = gst.parse_launch(
            ' ! '.join(self.parse_launch_array))

    def run(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus_name = dbus.service.BusName(
            "com.example.service", dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, "/com/example/service")

        self.ready()

        listener = self.pipeline.get_by_name('listener')
        listener.connect('result', self.__result__)
        listener.set_property('configured', True)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::application', self.__application_message__)

        self.pipeline.set_state(gst.STATE_PLAYING)

        self._loop = gobject.MainLoop()
        print "ScarlettListener running..."
        self._loop.run()
        print "ScarlettListener stopped"

    @dbus.service.method("com.example.service.Message", in_signature='', out_signature='s')
    def get_message(self):
        print "  sending message"
        return self._message

    @dbus.service.method("com.example.service.Quit", in_signature='', out_signature='')
    def quit(self):
        print "  shutting down"
        self._loop.quit()

    def partial_result(self, asr, text, uttid):
        """Forward partial result signals on the bus to the main thread."""
        pass

    def result(self, hyp, uttid):
        """Forward result signals on the bus to the main thread."""
        logger.debug(Fore.YELLOW + "Inside result function")
        if hyp in self.config.get('scarlett', 'keywords'):
            logger.debug(
                Fore.YELLOW +
                "HYP-IS-SOMETHING: " +
                hyp +
                "\n\n\n")
            logger.debug(
                Fore.YELLOW +
                "UTTID-IS-SOMETHING:" +
                uttid +
                "\n")
            self.failed = 0
            self.kw_found = 1

            # TODO: Change this to emit to main thread
            # scarlett.basics.voice.play_block('pi-listening')

        else:
            failed_temp = self.failed + 1
            self.failed = failed_temp
            logger.debug(
                Fore.YELLOW +
                "self.failed = %i" %
                (self.failed))
            if self.failed > 4:
                # reset pipline
                self.scarlett_reset_listen()
                # TODO: Change this to emit text data to main thread
                # ScarlettTalk.speak(
                #     " %s , if you need me, just say my name." %
                #     (self.config.get('scarlett', 'owner')))

    def run_cmd(self, hyp, uttid):
        logger.debug(Fore.YELLOW + "Inside run_cmd function")
        logger.debug(Fore.YELLOW + "KEYWORD IDENTIFIED BABY")
        logger.debug(
            Fore.RED +
            "self.kw_found = %i" %
            (self.kw_found))
        if hyp == 'CANCEL':
            self.cancel_listening()
        else:
            # TODO: Change this to dbus signal
            # TODO: hyp_event = scarlett_event(
            # TODO:     "listener_hyp",
            # TODO:     data=hyp
            # TODO: )
            # TODO: self.emit('kw-found-ps', hyp_event)

            current_kw_identified = self.kw_found
            self.kw_found = current_kw_identified

            logger.debug(
                Fore.RED +
                "AFTER run_cmd, self.kw_found = %i" %
                (self.kw_found))

    def hello(self):
        print 'hello hello hello!'

    def listen(self, valve, vader):
        logger.debug(Fore.YELLOW + "Inside listen function")
        # TODO: have this emit pi-listening to mainthread
        # scarlett.basics.voice.play_block('pi-listening')
        valve.set_property('drop', False)
        valve.set_property('drop', True)

    def cancel_listening(self):
        logger.debug(Fore.YELLOW + "Inside cancel_listening function")
        self.scarlett_reset_listen()
        logger.debug(Fore.YELLOW + "self.failed = %i" % (self.failed))
        logger.debug(
            Fore.RED +
            "self.keyword_identified = %i" %
            (self.kw_found))

    def get_hmm_full_path(self):
        if os.environ.get('SCARLETT_HMM'):
            _hmm_full_path = os.environ.get('SCARLETT_HMM')
        else:
            _hmm_full_path = self.config.get('pocketsphinx', 'hmm')

        return _hmm_full_path

    def get_lm_full_path(self):
        if os.environ.get('SCARLETT_LM'):
            _lm_full_path = os.environ.get('SCARLETT_LM')
        else:
            _lm_full_path = self.config.get('pocketsphinx', 'lm')

        return _lm_full_path

    def get_dict_full_path(self):
        if os.environ.get('SCARLETT_DICT'):
            _dict_full_path = os.environ.get('SCARLETT_DICT')
        else:
            _dict_full_path = self.config.get('pocketsphinx', 'dict')

        return _dict_full_path

    def get_pipeline(self):
        logger.debug(Fore.YELLOW + "Inside get_pipeline")
        return self.pipeline

    def get_pipeline_state(self):
        return self.pipeline.get_state()

    def _get_pocketsphinx_definition(self, override_parse):
        logger.debug(Fore.YELLOW + "Inside _get_pocketsphinx_definition")
        """Return ``pocketsphinx`` definition for :func:`gst.parse_launch`."""
        # default, use what we have set
        if override_parse == '':
            return [
                'alsasrc device=' +
                self.ps_device,
                'queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0',  # noqa
                'audioconvert',
                'audioresample',
                'audio/x-raw-int, rate=16000, width=16, depth=16, channels=1',
                'audioresample',
                'audio/x-raw-int, rate=8000',
                'vader name=vader auto-threshold=true',
                'pocketsphinx lm=' +
                self.ps_lm +
                ' dict=' +
                self.ps_dict +
                ' hmm=' +
                self.ps_hmm +
                ' name=listener',
                'fakesink dump=1']
            # NOTE, I commented out the refrence to the tee
            # 'fakesink dump=1 t.'
        else:
            return override_parse

    def _get_vader_definition(self):
        logger.debug(Fore.YELLOW + "Inside _get_vader_definition")
        """Return ``vader`` definition for :func:`gst.parse_launch`."""
        # source: https://github.com/bossjones/eshayari/blob/master/eshayari/application.py # noqa
        # Convert noise level from spin button range [0,32768] to gstreamer
        # element's range [0,1]. Likewise, convert silence from spin button's
        # milliseconds to gstreamer element's nanoseconds.

        # MY DEFAULT VADER DEFINITON WAS: vader name=vader auto-threshold=true
        # vader name=vader auto-threshold=true
        noise = 256 / 32768
        silence = 300 * 1000000
        return ("vader "
                + "name=vader "
                + "auto-threshold=false "
                + "threshold=%.9f " % noise
                + "run-length=%d " % silence
                )

    def _on_vader_start(self, vader, pos):
        logger.debug(Fore.YELLOW + "Inside _on_vader_start")
        """Send start position as a message on the bus."""
        import gst
        struct = gst.Structure("start")
        pos = pos / 1000000000  # ns to s
        struct.set_value("start", pos)
        vader.post_message(gst.message_new_application(vader, struct))

    def _on_vader_stop(self, vader, pos):
        logger.debug(Fore.YELLOW + "Inside _on_vader_stop")
        """Send stop position as a message on the bus."""
        import gst
        struct = gst.Structure("stop")
        pos = pos / 1000000000  # ns to s
        struct.set_value("stop", pos)

    def __result__(self, listener, text, uttid):
        """We're inside __result__"""
        logger.debug(Fore.YELLOW + "Inside __result__")
        import gst
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __partial_result__(self, listener, text, uttid):
        """We're inside __partial_result__"""
        logger.debug(Fore.YELLOW + "Inside __partial_result__")
        struct = gst.Structure('partial_result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __run_cmd__(self, listener, text, uttid):
        """We're inside __run_cmd__"""
        import gst
        logger.debug(Fore.YELLOW + "Inside __run_cmd__")
        struct = gst.Structure('result')
        struct.set_value('hyp', text)
        struct.set_value('uttid', uttid)
        listener.post_message(gst.message_new_application(listener, struct))

    def __application_message__(self, bus, msg):
        msgtype = msg.structure.get_name()
        logger.debug(Fore.YELLOW + "msgtype: " + msgtype)
        if msgtype == 'partial_result':
            self.partial_result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'result':
            if self.kw_found == 1:
                self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
            else:
                self.result(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == 'run_cmd':
            self.run_cmd(msg.structure['hyp'], msg.structure['uttid'])
        elif msgtype == gst.MESSAGE_EOS:
            pass
            # TODO: SEE IF WE NEED THIS
            # self.pipeline.set_state(gst.STATE_NULL)
        elif msgtype == gst.MESSAGE_ERROR:
            (err, debug) = msgtype.parse_error()
            logger.debug(Fore.RED + "Error: %s" % err, debug)
            pass

if __name__ == "__main__":
    logger = setup_logger()
    ScarlettListener("This is the ScarlettListener").run()
