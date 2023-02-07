#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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
import scarlett_constants


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

logger = setup_logger()


class ScarlettForecast():

    def __init__(self, config, cmd):
        global logger
        import forecastio
        self.config = config
        self.command = cmd
        self.lat = self.config.get('forecastio', 'lat')
        self.lng = self.config.get('forecastio', 'lng')
        self.api_key = self.config.get('forecastio', 'api_key')
        self.f = forecastio.load_forecast(self.api_key, self.lat, self.lng)

    def api(self):
        if self.command not in scarlett_constants.FORECAST_CMDS.keys():
            return
        logger.debug(
            f"** received {self.command}, sending 'forecast command: {scarlett_constants.FORECAST_CMDS[self.command]}'"
        )
        logger.debug(self.f.hourly().data[0].temperature)
        fio_hourly = f"{self.f.hourly().data[0].temperature} degrees fahrenheit"
        fio_hourly = fio_hourly.replace(";", "\;")

        logger.debug("===========Hourly Data=========")
        by_hour = self.f.hourly()
        logger.debug(f"Hourly Summary: {by_hour.summary}")
        fio_summary = f"Hourly Summary: {by_hour.summary}"
        fio_summary = fio_summary.replace(";", "\;")

        logger.debug("===========Daily Data=========")
        by_day = self.f.daily()
        logger.debug(f"Daily Summary: {by_day.summary}")
        fio_day = f"Daily Summary: {by_day.summary}"

        return (fio_hourly, fio_summary, fio_day)

    def quit(self):
        logger.debug("  shutting down ScarlettForecast")
