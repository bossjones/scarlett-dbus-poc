#!/usr/bin/env bash

# NOTE: OLD ALIASES
# alias keyword-found-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitKeywordRecognizedSignal.emitKeywordRecognizedSignal"'
# alias keyword-cancel-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitListenerCancelSignal.emitListenerCancelSignal"'
# alias command-weather-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitCommandRecognizedSignal.emitCommandRecognizedSignal" string:"WHAT IS THE WEATHER"'
# alias command-failed-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitSttFailedSignal.emitSttFailedSignal"'

alias keyword-found-signal='dbus-send --session --print-reply --dest="org.scarlett" "/org/scarlett/Listener" "org.scarlett.Listener.emitKeywordRecognizedSignal"'
alias keyword-cancel-signal='dbus-send --session --print-reply --dest="org.scarlett" "/org/scarlett/Listener" "org.scarlett.Listener.emitListenerCancelSignal"'
alias command-weather-signal='dbus-send --session --print-reply --dest="org.scarlett" "/org/scarlett/Listener" "org.scarlett.Listener.emitCommandRecognizedSignal" string:"WHAT IS THE WEATHER"'
alias command-failed-signal='dbus-send --session --print-reply --dest="org.scarlett" "/org/scarlett/Listener" "org.scarlett.Listener1.emitSttFailedSignal" string:"  ScarlettListener hit Max STT failures" string:"pi-response2"'

alias gsl-debug='GST_DEBUG=GST_REFCOUNTING:5 gst-launch-1.0'
alias open_dotfile='eog'
alias scarlett_open_dotfile='eog'

gst_debug_setup(){
  export GST_DEBUG_DUMP_DOT_DIR=/home/pi/dev/bossjones-github/scarlett-dbus-poc/_debug
}

gst_debug_convert_input(){
  dot -Tsvg $1 > output.svg
}

appsink_player_test() {
  _DIR=file:///home/pi/dev/bossjones-github/scarlett-dbus-poc/static/sounds

  gsl-debug uridecodebin uri=${_DIR}/pi-listening.wav ! \
                 tee name=t ! \
                 queue ! \
                 audioconvert ! \
                 appsink caps='audio/x-raw, format=(string)S16LE' \
                         drop=false max-buffers=10 sync=false \
                         emit-signals=true t. ! \
                 queue ! \
                 pulsesink sync=false >> log.txt 2>&1
}

appsink_player_test_orig() {
  _DIR=file:///home/pi/dev/bossjones-github/scarlett-dbus-poc/static/sounds
  gsl-debug uridecodebin uri=${_DIR}/pi-listening.wav ! \
            audioconvert ! \
            appsink caps='audio/x-raw, format=(string)S16LE' \
                    drop=false max-buffers=10 sync=false \
                    emit-signals=true
}

command-failed-signal(){
  # ORIG
  # dbus-send --session --print-reply --dest="org.scarlett" \
  #           "/org/scarlett/Listener" \
  #           "org.scarlett.Listener1.emitSttFailedSignal" \
  #            string:"  ScarlettListener hit Max STT failures" string:"pi-response2"
  dbus-send --session --print-reply --dest="org.scarlett" \
            "/org/scarlett/Listener" \
            "org.scarlett.Listener1.emitSttFailedSignal"

# ± |feature-new-gst-and-pocketsphinx U:11 ?:40 ✗| → dbus-send --session --print-reply --dest="org.scarlett" \
# >             "/org/scarlett/Listener" \
# >             "org.scarlett.Listener1.emitSttFailedSignal" \
# >              string:"  ScarlettListener hit Max STT failures" string:"pi-response2"
# Error org.freedesktop.DBus.Error.InvalidArgs: Type of message, '(ss)', does not match expected type '()'

}
            #
            #  dbus-send --dest=org.freedesktop.ExampleName               \
            #            /org/freedesktop/sample/object/name              \
            #            org.freedesktop.ExampleInterface.ExampleMethod   \
            #            int32:47 string:'hello world' double:65.32       \
            #            array:string:"1st item","next item","last item"  \
            #            dict:string:int32:"one",1,"two",2,"three",3      \
            #            variant:int32:-8                                 \
            #            objpath:/org/freedesktop/sample/object/name

# method call time=1460386682.377494 sender=:1.3 -> destination=org.scarlett serial=2 path=/org/scarlett/Listener; interface=org.scarlett.Listener1; member=emitSttFailedSignal
# signal time=1460386703.797934 sender=:1.0 -> destination=(null destination) serial=8 path=/org/scarlett/Listener; interface=org.scarlett.Listener; member=SttFailedSignal
#   string "  ScarlettListener hit Max STT failures"
#   string "pi-response2"


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
