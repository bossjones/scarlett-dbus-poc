#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# import dbus
# import pprint
# pp = pprint.PrettyPrinter(indent=4)

# # Proxy object from the object in receiver
# obj = dbus.SessionBus().get_object('com.example.service', '/com/example/service')

# pp.pprint(obj)
# print obj.KeywordRecognizedSignal(dbus_interface='tld.domain.sub.TestInterface', "  ScarlettListener caught a keyword match",
#                                   "pi-listening")


## <?xml version="1.0" encoding="UTF-8" ?>
##
## <node name="/">
##
##   <interface name="org.hexchat.connection">
##     <method name="Connect">
##       <annotation name="org.freedesktop.DBus.GLib.Async" value=""/>
##       <arg type="s" name="filename" direction="in"/>
##       <arg type="s" name="name" direction="in"/>
##       <arg type="s" name="desc" direction="in"/>
##       <arg type="s" name="version" direction="in"/>
##       <arg type="s" name="path" direction="out"/>
##     </method>
##     <method name="Disconnect">
##       <annotation name="org.freedesktop.DBus.GLib.Async" value=""/>
##     </method>
##   </interface>

from gi.repository import Gio

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
connection = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None,
              'com.example.service', '/com/example/service', 'com.example.service.event', None)
path = connection.Connect('(ssss)',
          'example.py',
          'Python example',
          'Example of a D-Bus client written in python',
          '1.0')
hexchat = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None,
                'org.hexchat.service', path, 'org.hexchat.plugin', None)

# Note the type before every arguement, this must be done.
# Type requirements are listed in our docs and characters are listed in the dbus docs.
# s = string, u = uint, i = int, etc.
