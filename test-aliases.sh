#!/usr/bin/env bash

alias keyword-found-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitKeywordRecognizedSignal.emitKeywordRecognizedSignal"'
alias keyword-cancel-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitListenerCancelSignal.emitListenerCancelSignal"'
alias command-weather-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitCommandRecognizedSignal.emitCommandRecognizedSignal" string:"WHAT IS THE WEATHER"'
alias command-failed-signal='dbus-send --session --print-reply --dest="com.example.service" "/com/example/service" "com.example.service.emitSttFailedSignal.emitSttFailedSignal"'
