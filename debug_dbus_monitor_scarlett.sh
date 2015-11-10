#!/usr/bin/env bash

dbus-monitor "type='signal',sender='com.example.service',interface='com.example.service'"
