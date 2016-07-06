#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement
from __future__ import division

import sys
import os

os.environ[
    "GST_DEBUG_DUMP_DOT_DIR"] = "/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug"
os.putenv('GST_DEBUG_DUMP_DIR_DIR',
          '/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug')

import pprint
pp = pprint.PrettyPrinter(indent=4)

from IPython.core.debugger import Tracer
from IPython.core import ultratb

sys.excepthook = ultratb.FormattedTB(mode='Verbose',
                                     color_scheme='Linux',
                                     call_pdb=True,
                                     ostream=sys.__stdout__)
import logging
logger = logging.getLogger('scarlettlogger')

import generator_utils
from generator_utils import trace, abort_on_exception

import time
import datetime

CMD_MASTER_LIST_HEX = {
    "frizzytv": {
        "up": "1,77E1D009,32",
        "down": "1,77E1B009,32",
        "left": "1,77E11009,32",
        "right": "1,77E1E009,32",
        "menu": "1,77E1BA09,32",
        "pause": "1,77E12009,32",
        "play": "1,77E17A09,32",
        "circle button": "1,77E1BA09,32"  # this too 77E12009
    },
    "appletv": {
        "up": "1,77E1D030,32",
        "down": "1,77E1B030,32",
        "left": "1,77E11030,32",
        "right": "1,77E1E030,32",
        "menu": "1,77E14030,32",
        "pause": "1,77E17A30,32",
        "play": "1,77E17A30,32",
        "circle button": "1,77E1BA30,32"
    },
    "toshiba": {
        "channel up": "1,2FDD827,32",
        "channel down": "1,2FDF807,32",
        "volume up": "1,2FD58A7,32",
        "volume down": "1,2FD7887,32",
        "mute": "1,2FD08F7,32",
        "recall": "1,2FD38C7,32",
        "input": "1,2FDF00F,32",
        "select up": "1,2FD41BE,32",
        "select down": "1,2FDC13E,32",
        "select left": "1,2FDB847,32",
        "select right": "1,2FD9867,32",
        "select enter": "1,2FD916E,32",
        "one": "1,2FD807F,32",
        "two": "1,2FD40BF,32",
        "three": "1,2FDC03F,32",
        "four": "1,2FD20DF,32",
        "five": "1,2FDA05F,32",
        "six": "1,2FD609F,32",
        "seven": "1,2FDE01F,32",
        "eight": "1,2FD10EF,32",
        "nine": "1,2FD906F,32",
        "zero": "1,2FD00FF,32",
        "power": "1,2FD48B7,32"
    }
}

SPOTIFY_CMDS = {
    "SPOTIFY PLAY": "play music",
    "SPOTIFY PAUSE": "pause music",
    "SPOTIFY SKIP": "skip track",
    "SPOTIFY SKIP FORWARD": "track back",
    "SPOTIFY SKIP BACK": "track forward",
}

LIGHT_CMDS = {
    "TURN ON THE LIGHTS": "hue lights on",
    "TURN ON LIGHTS": "hue lights on",
    "LIGHTS ON": "hue lights on",
    "TURN OFF THE LIGHTS": "hue lights off",
    "TURN OFF LIGHTS": "hue lights off",
    "LIGHTS OFF": "hue lights off",
    "TURN LIGHTS RED": "hue lights all red",
    "LIGHTS RED": "hue lights all red",
    "CHANGE LIGHTS RED": "hue lights all red",
    "TURN LIGHTS GREEN": "hue lights all green",
    "LIGHTS GREEN": "hue lights all green",
    "CHANGE LIGHTS GREEN": "hue lights all green",
    "TURN LIGHTS WHITE": "hue lights all white",
    "LIGHTS WHITE": "hue lights all white",
    "CHANGE LIGHTS WHITE": "hue lights all white",

    # TODO: CHANGE THIS BULLSHIT TO USE PROPER PYTHON MODULE
    "TURN LIGHTS BRIGHTER": "echo '{\"bri\": 240}' | hue lights 3 state",
    "LIGHTS BRIGHTER": "echo '{\"bri\": 240}' | hue lights 3 state",
    "TURN LIGHTS DARKER": "echo '{\"bri\": 100}' | hue lights 3 state",
    "LIGHTS DARKER": "echo '{\"bri\": 100}' | hue lights 3 state",
    "SEXY TIME": "hue lights colorloop",
    "GET LIGHT NAMES": "get light names",
}

TIME_CMDS = {
    "WHAT TIME IS IT": "what time is it",
    "TIME IS IT": "what time is it",
    "TIME IT IS": "what time is it"
}

TV_CMDS = {
    "CHANNEL UP": "channel up",
    "CHANNEL DOWN": "channel down",
    "TURN TO MTV": "turn to mtv",
    "TURN TO BET": "turn to bet",
    "TURN TO HBO": "turn to hbo",
    "SWITCH TO APPLE TV": "switch to apple tv",
    "SWITCH TO PLAY STATION": "switch to play station",
    "SWTICH TO REGULAR TV": "switch to regular tv",
    "APPLE TV UP": CMD_MASTER_LIST_HEX["appletv"]["up"].lower(),
    "APPLE TV CHANNEL UP": CMD_MASTER_LIST_HEX["appletv"]["up"].lower(),
    "APPLE TV DOWN": CMD_MASTER_LIST_HEX["appletv"]["down"].lower(),
    "APPLE TV CHANNEL DOWN": CMD_MASTER_LIST_HEX["appletv"]["down"].lower(),
    "APPLE TV LEFT": CMD_MASTER_LIST_HEX["appletv"]["left"].lower(),
    "APPLE TV CHANNEL LEFT": CMD_MASTER_LIST_HEX["appletv"]["left"].lower(),
    "APPLE TV RIGHT": CMD_MASTER_LIST_HEX["appletv"]["right"].lower(),
    "APPLE TV CHANNEL RIGHT": CMD_MASTER_LIST_HEX["appletv"]["right"].lower(),
    "APPLE TV PAUSE": CMD_MASTER_LIST_HEX["appletv"]["pause"].lower(),
    "APPLE TV PLAY": CMD_MASTER_LIST_HEX["appletv"]["play"].lower(),
    "APPLE TV MENU": CMD_MASTER_LIST_HEX["appletv"]["menu"].lower(),
    "APPLE TV MENU BUTTON": CMD_MASTER_LIST_HEX["appletv"]["menu"].lower(),
    "APPLE TV ENTER": CMD_MASTER_LIST_HEX["appletv"]["circle button"].lower(),
    "APPLE TV ENTER BUTTON": CMD_MASTER_LIST_HEX["appletv"]["circle button"].lower()
}

GENERAL_CMDS = {
    "CANCEL": "cancel",
}

FORECAST_CMDS = {
    "WHAT IS THE FORECAST": "weather",
    "WHAT IS THE TEMPATURE": "weather",
    "WHAT IS CURRENT TEMPATURE": "weather",
    "WHATS THE WEATHER": "weather",
    "WHATS TODAYS WEATHER": "weather",
    "WHATS THE TEMPATURE": "weather",
}

NO_OP = '__SCARLETT_NO_OP__'

######################################################################################################################
# NOTE: In the future time will be its own plugin class etc, for now we're just going to add arbitrary functions here:
######################################################################################################################
######################################################################################################################


class TimeCommand(object):

    @staticmethod
    def get_current_time():
        now = datetime.datetime.now()
        return now.strftime("It is now, %I:%M %p")

    @staticmethod
    def get_current_date():
        now = datetime.datetime.now()
        return now.strftime("Today's date is, %A, %B %d, %Y")

######################################################################################################################
######################################################################################################################


class Command(object):

    @staticmethod
    def check_cmd(command_tuple=None):
        logger.error("Value of command_tuple: {}".format(command_tuple))

        if isinstance(command_tuple, tuple):
            logger.info("Valid command_tuple: {}".format(command_tuple))
        else:
            logger.error("INValid command_tuple: {}".format(command_tuple))
            return NO_OP

        msg, scarlett_sound, command = command_tuple

        if command in SPOTIFY_CMDS.keys():
            logger.debug("** received {}, sending 'spotify {}'".format(command, SPOTIFY_CMDS[command]))
        elif command in LIGHT_CMDS.keys():
            logger.debug("** received {}, sending 'light {}'".format(command, LIGHT_CMDS[command]))
            # try:
            #     logger.debug("trying light chit")
            #     self.get_hue = scarlett.connect_hue(self.voice, self.brain)
            #     return self.get_hue.get_light_names()
            #     # REFACTOR ### light_play(LIGHT_CMDS[command])
            # except Exception as e:
            #     logger.debug("light exception b. \nCMD: {} \nException: {}" %(command, e))
            #     # REFACTOR ### general_play("cancel")
        elif command in TIME_CMDS.keys():
            logger.debug("** received {}, sending 'time {}'".format(command, TIME_CMDS[command]))
            return TimeCommand.get_current_time()
            # try:
            #     from scarlett.features.time import FeatureTime
            #     self.get_time = FeatureTime(self.voice, self.brain)
            #     return self.get_time.time_play()
            # except Exception as e:
            #     logger.debug(
            #         "time exception b. \nCMD: {} \nException: {}" %
            #         (command, e))
        elif command in GENERAL_CMDS.keys():
            logger.debug("** received {}, sending 'general command: {}'".format(command, GENERAL_CMDS[command]))
        elif command in FORECAST_CMDS.keys():
            logger.debug("** received {}, sending 'forecast command: {}'".format(command, FORECAST_CMDS[command]))
        elif command in TV_CMDS.keys():
            logger.debug("** received {}, sending 'tv command: {}'".format(command, TV_CMDS[command]))
