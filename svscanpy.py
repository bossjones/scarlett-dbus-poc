#!/usr/bin/python

# source: https://github.com/patrys/daemontools-ng

from time import time
import dbus, dbus.service, gobject, os, signal, sys, threading
from dbus.mainloop.glib import DBusGMainLoop

class Service(dbus.service.Object):
    pid = 0
    path = ''
    dead = True # do we need to check the pid?
    paused = False
    lastDied = time() # last death timestamp
    respawn = True
    interval = 5.0 # avoid infinite restart loops
    parent = None
    name = ''
    okpipe = None
    commandpipe = None

    def taia_now(self):
        now = (long(time()) + 4611686018427387914) << 32
        ret = ''
        for i in range(11, -1, -1):
            ret += chr(now >> (i * 8) & 0xff)
        return ret

    def __init__(self, path, parent, name):
        super(Service, self).__init__(parent.busName, '/Services/' + name)
        self.name = name
        self.path = path
        self.parent = parent
        self.launch()

    def announce(self):
        '''
        Emulate daemontools for compatibility
        '''
        dir = os.path.join(self.path, 'supervise')
        if not os.path.isdir(dir):
            os.mkdir(dir, 0700)
        fifo = os.path.join(dir, 'ok')
        if not os.path.exists(fifo):
            os.mkfifo(fifo, 0600)
        if not self.okpipe:
            self.okpipe = open(fifo, 'r+')
        fifo = os.path.join(dir, 'control')
        if not os.path.exists(fifo):
            os.mkfifo(fifo, 0600)
        if not self.commandpipe:
            self.commandpipe = open(fifo, 'r+')
            gobject.io_add_watch(self.commandpipe, gobject.IO_IN, self.command)
        del fifo
        f = open(os.path.join(dir, 'status.new'), 'wb')
        f.write(self.taia_now())
        for i in range(4): # write pid
            if self.dead:
                f.write(chr(0))
            else:
                f.write(chr(self.pid >> (i * 8) & 0xff))
        if self.dead: # write paused flag
            f.write(chr(0))
        else:
            f.write(chr(self.paused))
        if not self.respawn: # write status
            f.write('d')
        else:
            f.write('u')
        f.close()
        os.rename(os.path.join(dir, 'status.new'), os.path.join(dir, 'status'))

    def command(self, fd, cond):
        '''
        Emulate daemontools' command fifo
        '''
        cmd = self.commandpipe.read(1)
        if cmd in ('d', 'x'):
            print 'die!'
            self.setRespawn(False)
            if self.paused:
                self.kill(signal.SIGCONT)
            self.kill(signal.SIGTERM)
        elif cmd == 'u':
            self.setRespawn(True)
            if self.dead:
                self.launch()
        elif cmd == 'o':
            self.setRespawn(False)
            if self.dead:
                self.launch()
        elif cmd == 'a':
            self.kill(signal.SIGALRM)
        elif cmd == 'h':
            self.kill(signal.SIGHUP)
        elif cmd == 'k':
            self.kill(signal.SIGKILL)
        elif cmd == 't':
            self.kill(signal.SIGTERM)
        elif cmd == 'i':
            self.kill(signal.SIGINT)
        elif cmd == 'p':
            self.kill(signal.SIGSTOP)
        elif cmd == 'c':
            self.kill(signal.SIGCONT)
        return True

    @dbus.service.signal(dbus_interface = 'com.github.patrys.Supervisor.Service', signature = 's')
    def changed(self, status):
        self.announce()

    def launch(self):
        '''
        Launch the service
        '''
        self.dead = False
        runner = os.path.join(self.path, 'run')
        if not os.path.exists(runner):
            self.lastDied = time()
            self.dead = True
            self.parent.log('unable to start %s: run does not exist' % self.path)
            return
        if not os.access(runner, os.X_OK):
            self.lastDied = time()
            self.dead = True
            self.parent.log('unable to start %s: run is not executable' % self.path)
            return
        self.parent.log('starting service: %s' % self.path)
        (self.pid, stdin, stdout, stderr) = gobject.spawn_async([runner], working_directory = self.path, flags = gobject.SPAWN_DO_NOT_REAP_CHILD)
        if self.pid <= 0:
            self.lastDied = time()
            self.dead = True
            self.parent.log('failed to start process: %s', self.path)
        else:
            gobject.child_watch_add(self.pid, self.died)
            self.changed('up')

    def setRespawn(self, respawn):
        '''
        Change the respawning flag
        '''
        self.respawn = respawn
        self.announce()

    @dbus.service.method(dbus_interface = 'com.github.patrys.Supervisor.Service', in_signature = 'u')
    def kill(self, sig):
        '''
        Send a signal
        '''
        if not self.dead:
            if sig == signal.SIGSTOP:
                self.paused = True
                self.changed('paused')
            elif sig == signal.SIGCONT:
                self.paused = False
                self.changed('up')
            os.kill(self.pid, sig)

    @dbus.service.method(dbus_interface = 'com.github.patrys.Supervisor.Service', out_signature = 'uusb')
    def status(self):
        '''
        Return status info
        '''
        if self.dead:
            msg = 'down'
        elif self.paused:
            msg = 'paused'
        else:
            msg = 'up'
        uptime = time() - self.lastDied
        return self.pid, uptime, msg, self.respawn

    def died(self, pid, cond, data = None):
        '''
        Catch a dying child
        '''
        self.parent.log('%s exited with status %s' % (self.path, cond))
        self.dead = True
        self.paused = False
        self.changed('down')
        if self.respawn:
            if time() - self.lastDied > self.interval:
                self.launch()
            else:
                self.parent.log('service %s respawning too fast, delaying' % self.path)
        else:
            self.parent.log('service %s will not be restarted' % self.path)
        self.lastDied = time()

    def check(self):
        '''
        Check service status and respawn it if needed
        '''
        if self.dead:
            if time() - self.lastDied >= self.interval and self.respawn:
                self.parent.log('respawning dead service: %s' % self.path)
                self.launch()

class Supervisor(dbus.service.Object):
    finished = False
    interval = 5
    directory = ''
    maxServices = 0
    services = {}
    busName = None

    def __init__(self, directory = '/service', maxServices = 1000):
        self.busName = dbus.service.BusName('com.github.patrys.Supervisor', bus = dbus.SessionBus())
        super(Supervisor, self).__init__(self.busName, '/Manager')
        self.directory = directory
        self.maxServices = maxServices
        gobject.timeout_add(self.interval * 1000, self.run)
        self.run()

    def log(self, string):
        sys.stderr.write(string + '\n')

    def scan(self):
        '''
        Search for services in a specified path and run them
        '''
        for f in os.listdir(self.directory):
            if f[0] == '.':
                continue
            path = os.path.join(self.directory, f)
            path = os.path.realpath(path)
            if path in self.services:
                continue
            if os.path.isdir(path) and not os.path.exists(os.path.join(path, 'down')):
                self.startService(path, f)

    def startService(self, path, name):
        '''
        Start a new service and supervise it
        '''
        path = os.path.realpath(path)
        if len(self.services) >= self.maxServices:
            self.log('unable to start %s: running too many services' % path)
            return
        if self.services.has_key(path):
            self.log('unable to start %s: already running' % path)
            return
        if os.path.exists(os.path.join(path, 'run')):
            service = Service(path, self, name)
            self.services[path] = service

    @dbus.service.method(dbus_interface = 'com.github.patrys.Supervisor', in_signature = 's', out_signature = 's')
    def find(self, path):
        path = os.realpath(path)
        if self.services.has_key(path):
            return '/Services/' . self.services[path].name
        else:
            return ''

    @dbus.service.method(dbus_interface = 'com.github.patrys.Supervisor', in_signature = '', out_signature = 'as')
    def list(self):
        return ['/Services/' + self.services[path].name for path in self.services.keys()]

    def shutdown(self):
        '''
        Terminate the whole process
        '''
        self.finished = True
        for srv in self.services.values():
            srv.setRespawn(False)
            srv.kill(signal.SIGTERM)

    def run(self):
        '''
        Idle loop - check for new services and restart dead ones
        '''
        if self.finished:
            return False
        self.scan()
        for srv in self.services.values():
            srv.check()
        return True

if __name__ == '__main__':
    DBusGMainLoop(set_as_default = True)
    s = Supervisor()
    try:
        gobject.MainLoop().run()
    finally:
        s.shutdown()
