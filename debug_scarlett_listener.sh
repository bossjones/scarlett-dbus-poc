#!/usr/bin/env bash

alias debug_scarlett_listener='cd ~/dev/bossjones-github/scarlett-dbus-poc/ && workon scarlett-dbus-poc && GST_DEBUG=3,python:5,gnl*:5 python scarlett_listener.py 2>&1 | tee listener.log'
