# scarlett-dbus-poc

Scarlett Dbus Listener Service implementation Proof-Of-Concept. 


Source: https://www.reddit.com/r/gnome/comments/3owhp6/python_help_critique_my_application_design_home/


### Simple python dbus example

Source: https://github.com/stylesuxx/python-dbus-examples

* Run dbus monitor and grep for the interesting output:

    dbus-monitor | grep /tld/domain/sub

* Run the receiver

Then you can either
* Run the invoker, which will call the proxxied receivers Test object methods.
* run the emitter, which will emit a test signal and a quit signal.

After running either of them, the receiver should be stopped.
