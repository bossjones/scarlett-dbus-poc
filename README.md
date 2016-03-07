# scarlett-dbus-poc

Scarlett Dbus Listener Service implementation Proof-Of-Concept.

Source: https://www.reddit.com/r/gnome/comments/3owhp6/python_help_critique_my_application_design_home/

# How to test scarlett_player

Open ipython and type the following:

```
In [1]: import scarlett_player

In [2]: scarlett_player.ScarlettPlayer("pi-listening").run()
```


### Simple python dbus example

Source: https://github.com/stylesuxx/python-dbus-examples

* Run dbus monitor and grep for the interesting output:

    dbus-monitor | grep /tld/domain/sub

* Run the receiver

Then you can either
* Run the invoker, which will call the proxxied receivers Test object methods.
* run the emitter, which will emit a test signal and a quit signal.

After running either of them, the receiver should be stopped.

### Vagrant packaging

# package the box
vagrant package --base scarlett-dbus-poc_default_1449512156423_85046 --output ~/ubuntu_14_04_base_w_gst_pulseaudio_guestadd2.box

# NOTE: WE SHOULD TRY RUNNING PACKAGE LIKE THIS
vagrant package --base scarlett-dbus-poc_default_1449512156423_85046 --output ~/ubuntu_14_04_base_w_gst_pulseaudio_guestadd3.box --vagrantfile ~/dev/bossjones/scarlett-dbus-poc/Vagrantfile

# add the box
vagrant box add --name "scarlettpi-base-ubuntu-14-04-pulse" /Users/malcolm/ubuntu_14_04_base_w_gst_pulseaudio_guestadd3.box

# reinstalling unity to make desktop work correctly again
http://askubuntu.com/questions/502224/dash-wont-launch-applications-after-upgrade-to-14-04

# new way to install
https://github.com/cmusphinx/pocketsphinx
https://github.com/cmusphinx/cmudict
https://github.com/cmusphinx/pocketsphinx-python
https://github.com/cmusphinx/sphinxbase
https://github.com/cmusphinx/sphinxtrain
https://github.com/cmusphinx/cmudict-tools
https://github.com/cmusphinx/kaldi


### dbus.con.emit_signal() example and breakdown

```
# Important reading:   https://wiki.gnome.org/action/show/Projects/PyGObject/IntrospectionPorting?action=show&redirect=PyGObject/IntrospectionPorting
devhelp command on ubuntu 15.10

# Assume c code looks like:
gboolean
g_dbus_connection_emit_signal (GDBusConnection *connection,
                               const gchar *destination_bus_name,
                               const gchar *object_path,
                               const gchar *interface_name,
                               const gchar *signal_name,
                               GVariant *parameters,
                               GError **error);

# ... where ...
Parameters:
  connection
    a GDBusConnection

  destination_bus_name
    the unique bus name for the destination for the signal or NULL to emit to all listeners.

  object_path
    path of remote object

  interface_name
    D-Bus interface to emit a signal on

  signal_name
    the name of the signal to emit

  parameters
    a GVariant tuple with parameters for the signal or NULL if not passing parameters.

  error
    Return location for error or NULL

  Return value
    TRUE unless error is set


# Then the python version looks like:
listener_rdy_status = GLib.Variant("(ss)", (message, scarlett_sound))
bus.emit_signal(None,
                '/org/scarlett/Listener',
                'org.scarlett.Listener',
                'ListenerReadySignal',
                listener_rdy_status)
```

# Client -> Service issue:

```
# Currently getting the following issue when proxy tries to connet:

method call time=1455504495.425644 sender=:1.49 -> destination=org.freedesktop.DBus serial=1 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=Hello
method return time=1455504495.425676 sender=org.freedesktop.DBus -> destination=:1.49 serial=1 reply_serial=1
   string ":1.49"
signal time=1455504495.425695 sender=org.freedesktop.DBus -> destination=(null destination) serial=203 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameOwnerChanged
   string ":1.49"
   string ""
   string ":1.49"
signal time=1455504495.425726 sender=org.freedesktop.DBus -> destination=:1.49 serial=2 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=NameAcquired
   string ":1.49"
method call time=1455504495.426215 sender=:1.4 -> destination=org.freedesktop.DBus serial=165 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=GetConnectionUnixProcessID
   string ":1.49"
method return time=1455504495.426264 sender=org.freedesktop.DBus -> destination=:1.4 serial=204 reply_serial=165
   uint32 27637
method call time=1455504495.428239 sender=:1.49 -> destination=org.freedesktop.DBus serial=2 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=AddMatch
   string "type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',member='NameOwnerChanged',path='/org/freedesktop/DBus',arg0='org.scarlett.Listener.SttFailedSignal'"
method return time=1455504495.428292 sender=org.freedesktop.DBus -> destination=:1.49 serial=3 reply_serial=2
method call time=1455504495.428302 sender=:1.49 -> destination=org.freedesktop.DBus serial=3 path=/org/freedesktop/DBus; interface=org.freedesktop.DBus; member=GetNameOwner
   string "org.scarlett.Listener.SttFailedSignal"
error time=1455504495.428320 sender=org.freedesktop.DBus -> destination=:1.49 error_name=org.freedesktop.DBus.Error.NameHasNoOwner reply_serial=3
   string "Could not get owner of name 'org.scarlett.Listener.SttFailedSignal': no such name"
method call time=1455504495.428336 sender=:1.49 -> destination=org.scarlett serial=4 path=/org/scarlett; interface=org.freedesktop.DBus.Introspectable; member=Introspect
method return time=1455504495.428346 sender=:1.48 -> destination=:1.49 serial=12 reply_serial=4
   string "<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
                      "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<!-- GDBus 2.46.2 -->
<node>
  <node name="Listener"/>
</node>
"

# THIS IS A PROPER SIGNAL EMIT
signal time=1455504580.676030 sender=:1.48 -> destination=(null destination) serial=13 path=/org/scarlett/Listener; interface=org.scarlett.Listener.SttFailedSignal; member=SttFailedSignal
   string "  ScarlettListener hit Max STT failures"
   string "pi-response2"
```

# FYI

```
In [38]: ss = bus.get("org.scarlett", object_path='/org/scarlett/Listener')

In [39]: ss.
ss.Get                          ss.emitCommandRecognizedSignal
ss.GetAll                       ss.emitConnectedToListener
ss.GetMachineId                 ss.emitKeywordRecognizedSignal
ss.Introspect                   ss.emitListenerCancelSignal
ss.Message                      ss.emitListenerReadySignal
ss.Ping                         ss.emitSttFailedSignal
ss.Set

In [39]: ss.
ss.Get                          ss.emitCommandRecognizedSignal
ss.GetAll                       ss.emitConnectedToListener
ss.GetMachineId                 ss.emitKeywordRecognizedSignal
ss.Introspect                   ss.emitListenerCancelSignal
ss.Message                      ss.emitListenerReadySignal
ss.Ping                         ss.emitSttFailedSignal
ss.Set

In [39]: exit
```

# Use this to figure out why foo ... which is suppose to just return a string, returns a ("string",) instead:

```
In [38]: foo_client = bus.get('net.lvht', object_path='/net/lvht/Foo')

In [39]: foo_client
Out[39]: <pydbus.bus.CompositeObject at 0x7f969770a6d0>

In [40]: foo_client.
foo_client.Get           foo_client.GetAll        foo_client.GetMachineId  foo_client.HelloWorld    foo_client.Introspect    foo_client.Ping          foo_client.Set

In [40]: foo_client.
foo_client.Get           foo_client.GetAll        foo_client.GetMachineId  foo_client.HelloWorld    foo_client.Introspect    foo_client.Ping          foo_client.Set

In [40]: foo_client.HelloWorld
Out[40]: <bound method CompositeObject.HelloWorld of <pydbus.bus.CompositeObject object at 0x7f969770a6d0>>

In [41]: foo_client.HelloWorld('hello',1)
Out[41]: ('hello1',)

In [42]:
```

# Looks like the in/out variables look incorrect:

```
(MainThread) DEBUG    Inside self.method_inargs and self.method_outargs
{   'Message': (),
    'emitCommandRecognizedSignal': ('s',),
    'emitConnectedToListener': ('s',),
    'emitKeywordRecognizedSignal': (),
    'emitListenerCancelSignal': (),
    'emitListenerReadySignal': (),
    'emitSttFailedSignal': ()}
{   'Message': '(s)',
    'emitCommandRecognizedSignal': '(s)',
    'emitConnectedToListener': '((s))',
    'emitKeywordRecognizedSignal': '(s)',
    'emitListenerCancelSignal': '(s)',
    'emitListenerReadySignal': '(s)',
    'emitSttFailedSignal': '(s)'}

# with xml

<node>
  <interface name='org.scarlett.Listener1'>
    <method name='emitKeywordRecognizedSignal'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <method name='emitCommandRecognizedSignal'>
      <arg type='s' name='command' direction='in'/>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <method name='emitSttFailedSignal'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <method name='emitListenerCancelSignal'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <method name='emitListenerReadySignal'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <method name='emitConnectedToListener'>
      <arg type='s' name='scarlett_plugin' direction='in'/>
      <arg type='(s)' name='s_cmd' direction='out'/>
    </method>
    <method name='Message'>
      <arg type='s' name='s_cmd' direction='out'/>
    </method>
    <signal name='KeywordRecognizedSignal'>
      <arg type='(ss)' name='kw_rec_status' direction='out'/>
    </signal>
    <signal name='CommandRecognizedSignal'>
      <arg type='(sss)' name='cmd_rec_status' direction='out'/>
    </signal>
    <signal name='SttFailedSignal'>
      <arg type='(ss)' name='stt_failed_status' direction='out'/>
    </signal>
    <signal name='ListenerCancelSignal'>
      <arg type='(ss)' name='listener_cancel_status' direction='out'/>
    </signal>
    <signal name='ListenerReadySignal'>
      <arg type='(ss)' name='listener_rdy_status' direction='out'/>
    </signal>
    <signal name='ConnectedToListener'>
      <arg type='(s)' name='conn_to_lis_status' direction='out'/>
    </signal>
  </interface>
</node>
```

```
# compared to foo.py
(MainThread) DEBUG    Inside self.method_inargs and self.method_outargs
(MainThread) DEBUG    Inside self.method_inargs
{   'HelloWorld': ('a', 'b')}
(MainThread) DEBUG    Inside self.method_outargs
{   'HelloWorld': '(s)'}

# with XML that looks like

<node>
	<interface name='net.lvht.Foo1'>
		<method name='HelloWorld'>
			<arg type='s' name='a' direction='in'/>
			<arg type='i' name='b' direction='in'/>
			<arg type='s' name='c' direction='out'/>
			<arg type='s' name='d' direction='out'/>
		</method>
	</interface>
</node>
```

# we are finally closer to getting signals read in and acted upon!!

```
'GStreamer 1.6.0'
********************************************************
(MainThread) DEBUG    ss PrettyPrinter:
<pydbus.bus.CompositeObject object at 0x7f817ed1dd90>
(MainThread) DEBUG    player_cb PrettyPrinter:
(   <DBusConnection object at 0x7f817ed787d0 (GDBusConnection at 0x22e2010)>,
    ':1.88',
    '/org/scarlett/Listener',
    'org.scarlett.Listener',
    'SttFailedSignal',
    GLib.Variant('(ss)', ('  ScarlettListener hit Max STT failures', 'pi-response2')))
---------------------------------------------------------------------------
ValueError                                Traceback (most recent call last)
/home/pi/dev/bossjones-github/scarlett-dbus-poc/test_gdbus_proxy_service.py in player_cb(*args=(<DBusConnection object at 0x7f817ed787d0 (GDBusConnection at 0x22e2010)>, ':1.88', '/org/scarlett/Listener', 'org.scarlett.Listener', 'SttFailedSignal', GLib.Variant('(ss)', ('  ScarlettListener hit Max STT failures', 'pi-response2'))), **kwargs={})
     99     pp = pprint.PrettyPrinter(indent=4)
    100     pp.pprint(args)
--> 101     msg, scarlett_sound = args
        msg = undefined
        scarlett_sound = undefined
        args = (<DBusConnection object at 0x7f817ed787d0 (GDBusConnection at 0x22e2010)>, ':1.88', '/org/scarlett/Listener', 'org.scarlett.Listener', 'SttFailedSignal', GLib.Variant('(ss)', ('  ScarlettListener hit Max STT failures', 'pi-response2')))
    102     logger.warning(" msg: {}".format(msg))
    103     logger.warning(" scarlett_sound: {}".format(scarlett_sound))

ValueError: too many values to unpack
> /home/pi/dev/bossjones-github/scarlett-dbus-poc/test_gdbus_proxy_service.py(101)player_cb()
     99     pp = pprint.PrettyPrinter(indent=4)
    100     pp.pprint(args)
--> 101     msg, scarlett_sound = args
    102     logger.warning(" msg: {}".format(msg))
    103     logger.warning(" scarlett_sound: {}".format(scarlett_sound))

ipdb>
```

## Got signal emit + callback working. player_cb / command_cb

```
Service: python test_gdbus_simple_service.py

Tasker: python test_gdbus_proxy_service.py
```

### Got full emit + subscribe [02/21/2016] / No Threads + No Player / Speaker yet

```
Service: python test_gdbus_service.py

Tasker: python test_gdbus_proxy_service.py
```

## Beginning threading tasker fixes 3/6/2016

### TODO:

- [X] Listener. Good-to-go.
- [ ] Tasker
   - [ ] Threading
   - [ ] Calls to Player
   - [ ] Calls to Speaker
   - [ ] Calls to Features
- [ ] Player
- [ ] Speaker
- [ ] Brain
- [ ] Features
  - [ ] Forecast
  - [ ] GstUtils
  - [ ] Timer
  - [ ] Wordnik
  - [ ] Stocks
  - [ ] News
  - [ ] Lights
  - [ ] Music
  - [ ] TV
  - [ ] Sound
  - [ ] Blinds
