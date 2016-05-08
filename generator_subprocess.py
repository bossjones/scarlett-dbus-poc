# -*- coding: utf-8 -*-
# Copyright: 2007-2013, Sebastian Billaudelle <sbillaudelle@googlemail.com>
#            2010-2013, Kristoffer Kleine <kris.kleine@yahoo.de>

# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import os
import sys
import logging
from gi.repository import GObject, GLib


logger = logging.getLogger('scarlettlogger')

def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

class SubProcessError(Exception):
    pass


class TimeOutError(Exception):
    pass


class Subprocess(GObject.GObject):
    """
    GObject API for handling child processes.

    :param command: The command to be run as a subprocess.
    :param fork: If `True` this process will be detached from its parent and
                 run independent. This means that no excited-signal will be emited.

    :type command: `list`
    :type fork: `bool`
    """

    __gtype_name__ = 'Subprocess'
    __gsignals__ = {
        'exited': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT, GObject.TYPE_INT))
    }

    def __init__(self, command, name=None, fork=False):

        GObject.GObject.__init__(self)

        self.process = None
        self.pid = None

        if not fork:
            self.stdout = True
            self.stderr = True
        else:
            self.stdout = False
            self.stderr = False

        types = map(type, command)
        if not (min(types) == max(types) == str):
            raise TypeError("executables and arguments must be str objects")
        logger.debug("Running %r" % " ".join(command))

        self.command = command
        self.name = name
        self.forked = fork

        logger.debug("command: ".format(self.command))
        logger.debug("name: ".format(self.name))
        logger.debug("forked: ".format(self.forked))
        logger.debug("process: ".format(self.process))
        logger.debug("pid: ".format(self.pid))

        if fork:
            self.fork()

    def run(self):
        """ Run the process. """

        # NOTE: DO_NOT_REAP_CHILD: the child will not be automatically reaped;
        # you must use g_child_watch_add yourself (or call waitpid or handle `SIGCHLD` yourself),
        # or the child will become a zombie.
        # source:
        # http://valadoc.org/#!api=glib-2.0/GLib.SpawnFlags.DO_NOT_REAP_CHILD

        # NOTE: SEARCH_PATH: argv[0] need not be an absolute path, it will be looked for in the user’s PATH
        # source:
        # http://lazka.github.io/pgi-docs/#GLib-2.0/flags.html#GLib.SpawnFlags.SEARCH_PATH

        self.pid, self.stdin, self.stdout, self.stderr = GLib.spawn_async(self.command,
                                                                          flags=GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD
                                                                          )

        logger.debug("command: ".format(self.command))
        logger.debug("stdin: ".format(self.stdin))
        logger.debug("stdout: ".format(self.stdout))
        logger.debug("stderr: ".format(self.stderr))
        logger.debug("pid: ".format(self.pid))

        # close file descriptor
        self.pid.close()

        print self.stderr

        # NOTE: GLib.PRIORITY_HIGH = -100
        # Use this for high priority event sources.
        # It is not used within GLib or GTK+.
        watch = GLib.child_watch_add(GLib.PRIORITY_HIGH, self.pid, self.exited_cb)

        return self.pid

    def exited_cb(self, pid, condition):
        if not self.forked:
            logger.debug('exited', pid, condition)
            self.emit('exited', pid, condition)

    def fork(self):
        try:
            # first fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.exit(1)

        os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            # second fork
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError, e:
            sys.exit(1)
