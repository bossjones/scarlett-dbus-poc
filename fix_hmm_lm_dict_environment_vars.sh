#!/usr/bin/env bash

###
# hmm fix
###

sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' ~/.scarlett_aliases;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /home/pi/.virtualenvs/scarlett-dbus-poc/bin/postactivate;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/create_symlinks_virtualenv.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_cairo.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_glib.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_gst-plugins-espeak.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_gst-python.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_pocketsphinx-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_pocketsphinx.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_pygobject.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_sphinxbase-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/model/hmm/en_US/hub4wsj_sc_8k,/home/pi/.virtualenvs/scarlett-dbus-poc/share/pocketsphinx/model/en-us/en-us,g' /usr/local/bin/install_sphinxbase.sh

###
# lm fix
###

sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' ~/.scarlett_aliases;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /home/pi/.virtualenvs/scarlett-dbus-poc/bin/postactivate;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/create_symlinks_virtualenv.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_cairo.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_glib.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_gst-plugins-espeak.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_gst-python.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_pocketsphinx-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_pocketsphinx.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_pygobject.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_sphinxbase-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/lm/1602.lm,$MAIN_DIR/tests/fixtures/lm/1473.dic,g' /usr/local/bin/install_sphinxbase.sh


###
# dic fix
###

sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' ~/.scarlett_aliases;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /home/pi/.virtualenvs/scarlett-dbus-poc/bin/postactivate;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/create_symlinks_virtualenv.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_cairo.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_glib.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_gst-plugins-espeak.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_gst-python.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_pocketsphinx-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_pocketsphinx.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_pygobject.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_sphinxbase-0.8.sh;
sed -i 's,$MAIN_DIR/tests/fixtures/dict/1602.dic,$MAIN_DIR/tests/fixtures/dict/1473.dic,g' /usr/local/bin/install_sphinxbase.sh
