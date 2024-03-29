#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import gi
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
import inspect

from gi.importer import modules

# ScarlettDbusUtils = modules['ScarlettDbusUtils']._introspection_module
__all__ = []

#
# The following GDBus wrapper is based upon code by Martin Pitt from
# https://bugzilla.gnome.org/show_bug.cgi?id=656330
# demo D-Bus server using GDBus
# (C) 2010 Martin Pitt <martin@piware.de>
#

class _Gio_DBusMethodInfo:
    interface = None
    in_args = None
    out_signature = None

def DBusMethod(dbus_interface, in_signature=None, out_signature=None, async=False):
    def decorator(func):
        func._is_async = async

        func._dbus_method = _Gio_DBusMethodInfo()
        func._dbus_method.interface = dbus_interface
        #func._dbus_method.out_signature = '(' + (out_signature or '') + ')'
        func._dbus_method.out_signature = out_signature or ''

        func._dbus_method.in_args = []
        in_signature_list = GLib.Variant.split_signature(f'({in_signature})')
        arg_names = inspect.getargspec(func).args
        arg_names.pop(0) # eat "self" argument
        if async: arg_names.pop(0) # eat "invocation"
        if len(in_signature) != len(arg_names):
            raise TypeError(
                f'specified signature {str(in_signature_list)} for method {func.func_name} does not match length of arguments'
            )
        for pair in zip(in_signature_list, arg_names):
            func._dbus_method.in_args.append(pair)
        return func

    return decorator

class DBusService:
    class _DBusInfo:
        object_path = None
        connection = None
        reg_id = None
        methods = None # interface -> method_name -> info_map
                       # info_map keys: method_name, in_signature, out_signature

    def __init__(self, object_path=None):
        self.__dbus_info = self.__class__._DBusInfo()
        self.__dbus_info.object_path = object_path

        # set up the vtable maps, for more efficient lookups at runtime
        self.__dbus_info.methods = {}
        for id in dir(self):
            attr = getattr(self, id)
            if hasattr(attr, '_dbus_method'):
                self.__dbus_info.methods.setdefault(attr._dbus_method.interface, {})[id] = {
                    'in_args': attr._dbus_method.in_args,
                    'out_signature': attr._dbus_method.out_signature,
                }

    def export(self, connection, object_path=None):
        """
        @connection: A Gio.DBusConnection
        @object_path: an optional path to register at
        Exports the service onto the Gio.DBusConnection provided.
        If @object_path is None, then the object path registered during object
        creation will be used.
        """
        self.__dbus_info.connection = connection
        node_info = Gio.DBusNodeInfo.new_for_xml(self.__dbus_introspection_xml())
        for interface in self.__dbus_info.methods:
            self.__dbus_info.reg_id = connection.register_object(
                    object_path or self.__dbus_info.object_path,
                    node_info.lookup_interface(interface),
                    self.__dbus_method_call,
                    self.__dbus_get_property,
                    self.__dbus_set_property)

    def unexport(self):
        """
        Unregisters a previous registration to a connection using
        export_object().
        """
        self.connection.unregister_object(self.__dbus_info.reg_id)
        self.__dbus_info.reg_id = None
        self.__dbus_info.connection = None

    def __dbus_introspection_xml(self):
        '''Generate introspection XML'''
        parts = ['<node>']
        for interface in self.__dbus_info.methods:
            parts.append(f'  <interface name="{interface}">')
            for method, data in self.__dbus_info.methods[interface].items():
                parts.append(f'    <method name="{method}">')
                parts.extend(
                    f'      <arg type="{sig}" name="{name}" direction="in"/>'
                    for sig, name in data['in_args']
                )
                parts.extend(
                    (
                        f"""      <arg type="{data['out_signature']}" name="return" direction="out"/>""",
                        '    </method>',
                    )
                )
            parts.append('  </interface>')
        parts.append('</node>')
        return '\n'.join(parts)

    def __dbus_method_call(self, conn, sender, object_path, iface_name, method_name, parameters, invocation):
        try:
            info = self.__dbus_info.methods[iface_name][method_name]
        except KeyError:
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f'No such interface or method: {iface_name}.{method_name}',
            )
            return

        try:
            func = getattr(self, method_name)
            if func._is_async:
                ret = func(invocation, *parameters.unpack())
            else:
                ret = func(*parameters.unpack())
                invocation.return_value(GLib.Variant('(' + info['out_signature'] + ')', (ret,)))
        except Exception as e:
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.IO_ERROR,
                f'Method {iface_name}.{method_name} failed with: {str(e)}',
            )

    def __dbus_get_property(self, conn, sender, object_path, iface_name, prop_name, error):
        error = GLib.Error.new_literal(GLib.io_channel_error_quark(), 1, 'Not implemented yet')
        return None

    def __dbus_set_property(self, conn, sender, object_path, iface_name, prop_name, value, error):
        error = GLib.Error.new_literal(GLib.io_channel_error_quark(), 1, 'Not implemented yet')
        return False

ScarlettDbusUtils.DBusService = DBusService
ScarlettDbusUtils.DBusMethod = DBusMethod

# hergertme, question for you, I want to use some of the work you did in https://git.gnome.org/browse/gnome-builder/tree/libide/Ide.py to a project i'm working on, specifically to add async method support ...

# bossjones, i did some extension to a python-based GDBusServer as well here: https://git.gnome.org/browse/gnome-builder/tree/libide/Ide.py
