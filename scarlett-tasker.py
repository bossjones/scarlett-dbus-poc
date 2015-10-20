#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import dbus


class ScarlettTasker():

    def __init__(self):
        bus = dbus.SessionBus()
        service = bus.get_object('com.example.service', "/com/example/service")
        self._message = service.get_dbus_method(
            'get_message', 'com.example.service.Message')
        self._quit = service.get_dbus_method(
            'quit', 'com.example.service.Quit')

    def run(self):
        print "Mesage from service:", self._message()
        self._quit()

if __name__ == "__main__":
    ScarlettTasker().run()
