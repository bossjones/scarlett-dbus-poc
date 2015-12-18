#!/usr/bin/env bash

alias keyword-found-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitKeywordRecognizedSignal.emitKeywordRecognizedSignal"'
alias keyword-cancel-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitListenerCancelSignal.emitListenerCancelSignal"'
alias command-weather-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitCommandRecognizedSignal.emitCommandRecognizedSignal" string:"WHAT IS THE WEATHER"'
alias command-failed-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitSttFailedSignal.emitSttFailedSignal"'
alias open-dot='eog /home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug/scarlett-pipeline.png'
alias test-scarlett-gst='gst-launch-0.10 alsasrc device=hw:1 ! queue silent=false leaky=2 max-size-buffers=0 max-size-time=0 max-size-bytes=0 ! audioconvert ! audioresample ! audio/x-raw-int, rate=16000, width=16, depth=16, channels=1 ! audioresample ! audio/x-raw-int, rate=8000 ! vader name=vader auto-threshold=true ! pocketsphinx lm=/home/pi/dev/bossjones-github/scarlett/scarlett/static/speech/lm/1602.lm dict=/home/pi/dev/bossjones-github/scarlett/scarlett/static/speech/dict/1602.dic hmm=/usr/local/share/pocketsphinx/model/hmm/en_US/hub4wsj_sc_8k name=listener ! fakesink dump=1'
alias create-venv='mkvirtualenv scarlett-dbus-latest --system-site-packages'

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
