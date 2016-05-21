#!/usr/bin/env bash

export PI_HOME=/home/pi
export MAIN_DIR=$PI_HOME/dev/bossjones-github/scarlett-dbus-poc
export VIRT_ROOT=$PI_HOME/.virtualenvs/scarlett-dbus-poc
export PKG_CONFIG_PATH=$VIRT_ROOT/lib/pkgconfig
export SCARLETT_CONFIG=$MAIN_DIR/tests/fixtures/.scarlett
export SCARLETT_HMM=$PI_HOME/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us
export SCARLETT_LM=$MAIN_DIR/tests/fixtures/lm/1473.lm
export SCARLETT_DICT=$MAIN_DIR/tests/fixtures/dict/1473.dic
