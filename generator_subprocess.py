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
from gi.repository import GObject as gobject
# gobject.threads_init()
logger = logging.getLogger('scarlettlogger')


class Subprocess(gobject.GObject):
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
        'exited': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_INT))
    }

    def __init__(self, command, name=None, fork=False):

        gobject.GObject.__init__(self)

        self.process = None
        self.pid = None

        if not fork:
            self.stdout = True
            self.stderr = True
        else:
            self.stdout = False
            self.stderr = False

        self.command = command
        self.name = name
        self.forked = fork

        logger.debug(self.command)
        logger.debug(self.name)
        logger.debug(self.forked)
        logger.debug(self.process)
        logger.debug(self.pid)

        if fork:
            self.fork()

    def run(self):
        """ Run the process. """

        process_data = gobject.spawn_async(self.command,
                                           flags=gobject.SPAWN_SEARCH_PATH | gobject.SPAWN_DO_NOT_REAP_CHILD,
                                           standard_output=self.stdout,
                                           standard_error=self.stderr
                                           )

        self.pid = process_data[0]
        self.stdout = os.fdopen(process_data[2])
        self.stderr = os.fdopen(process_data[3])

        logger.debug(self.pid)
        logger.debug(self.stdout)
        logger.debug(self.stderr)

        print self.stderr

        self.watch = gobject.child_watch_add(self.pid, self.exited_cb)

        return self.pid

    def exited_cb(self, pid, condition):
        if not self.forked:
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
