#!/usr/bin/env bash

alias keyword-found-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitKeywordRecognizedSignal.emitKeywordRecognizedSignal"'
alias keyword-cancel-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitListenerCancelSignal.emitListenerCancelSignal"'
alias command-weather-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitCommandRecognizedSignal.emitCommandRecognizedSignal" string:"WHAT IS THE WEATHER"'
alias command-failed-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitSttFailedSignal.emitSttFailedSignal"'
alias open-dot='eog /home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/scarlett-pipeline.png'
alias test-scarlett-gst='gst-launch-0.10 alsasrc device=hw:1 ! queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0 ! audioconvert ! audioresample ! audio/x-raw-int, rate=16000, width=16, depth=16, channels=1 ! audioresample ! audio/x-raw-int, rate=8000 ! vader name=vader auto-threshold=true ! pocketsphinx lm=/home/pi/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/lm/1473.lm dict=/home/pi/dev/bossjones-github/scarlett-dbus-poc/tests/fixtures/dict/1473.dic hmm=/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us=listener ! fakesink dump=1'
alias create-venv='mkvirtualenv scarlett-dbus-poc --system-site-packages'

# functions
docker-machine-scarlett-create() {
  docker-machine create -d generic \
  --generic-ssh-user vagrant \
  --generic-ssh-key /Users/malcolm/dev/bossjones/scarlett-dbus-poc/.vagrant/machines/default/virtualbox/private_key \
  --generic-ip-address 127.0.0.1 \
  --generic-ssh-port 2222 \
  scarlett-docker
}

docker-pulse-audio(){
  docker run -d \
  -v /etc/localtime:/etc/localtime \
  -p 4713:4713 \
  --device /dev/snd \
  --name pulseaudio \
  jess/pulseaudio
}

docker-skype(){
  docker run -it \
  -v /etc/localtime:/etc/localtime \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -e DISPLAY=unix$DISPLAY \
  --device /dev/snd \
  --link pulseaudio:pulseaudio \
  -e PULSE_SERVER=pulseaudio \
  --device /dev/video0 \
  --name skype \
  jess/skype
}
