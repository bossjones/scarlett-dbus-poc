#!/usr/bin/env bash

# dbus-monitor "sender=com.example.service.******"
dbus-monitor "type='signal',sender='com.example.service',interface='com.example.service'"
