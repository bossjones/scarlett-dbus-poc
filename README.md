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
