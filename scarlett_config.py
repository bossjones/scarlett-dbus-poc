# -*- coding: utf-8 -*-
import StringIO
import os
import sys
import re
import ConfigParser
import signal
import pprint
pp = pprint.PrettyPrinter(indent=4)

# Config
try:
    os.path.expanduser('~')
    expanduser = os.path.expanduser
except (AttributeError, ImportError):
    # This is probably running on App Engine.
    expanduser = (lambda x: x)

# By default we use two locations for the scarlett configurations,
# /etc/scarlett.cfg and ~/.scarlett (which works on Windows and Unix).
ScarlettConfigPath = '/etc/scarlett.cfg'
UserConfigPath = os.path.join(expanduser('~'), '.scarlett')
ScarlettConfigLocations = [ScarlettConfigPath, UserConfigPath]
# If there's a SCARLETT_CONFIG variable set, we load ONLY
# that variable
if 'SCARLETT_CONFIG' in os.environ:
    ScarlettConfigLocations = [expanduser(os.environ['SCARLETT_CONFIG'])]

elif 'SCARLETT_PATH' in os.environ:
    ScarlettConfigLocations = [
        expanduser(path) for path in os.environ['SCARLETT_PATH'].split(":")
    ]


class Config(ConfigParser.SafeConfigParser):
    """Scarlett Config Class."""

    def __init__(self, path=None, fp=None, do_load=True):
        # We don't use ``super`` here, because ``ConfigParser`` still uses
        # old-style classes.
        ConfigParser.SafeConfigParser.__init__(
            self, {
                'working_dir': '/mnt/scarlett', 'debug': '0'})
        if do_load:
            if path:
                self.load_from_path(path)
            elif fp:
                self.readfp(fp)
            else:
                print 'Scarlett Config Path'
                pp.pprint(ScarlettConfigLocations)
                self.read(ScarlettConfigLocations)

    def load_from_path(self, path):
        file = open(path)
        for line in file.readlines():
            if match := re.match("^#import[\s\t]*([^\s^\t]*)[\s\t]*$", line):
                extended_file = match[1]
                (dir, file) = os.path.split(path)
                self.load_from_path(os.path.join(dir, extended_file))
        self.read(path)

    def save_option(self, path, section, option, value):
        """
        Write the specified Section.Option to the config file specified by path.
        Replace any previous value.  If the path doesn't exist, create it.
        Also add the option the the in-memory config.
        """
        config = ConfigParser.SafeConfigParser()
        config.read(path)
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
        with open(path, 'w') as fp:
            config.write(fp)
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, value)

    def save_user_option(self, section, option, value):
        self.save_option(UserConfigPath, section, option, value)

    def save_system_option(self, section, option, value):
        self.save_option(ScarlettConfigPath, section, option, value)

    def get_user(self, name, default=None):
        try:
            val = self.get('User', name)
        except:
            val = default
        return val

    def getint_user(self, name, default=0):
        try:
            val = self.getint('User', name)
        except:
            val = default
        return val

    def get_value(self, section, name, default=None):
        return self.get(section, name, default)

    def get(self, section, name, default=None):
        try:
            val = ConfigParser.SafeConfigParser.get(self, section, name)
        except:
            val = default
        return val

    def getint(self, section, name, default=0):
        try:
            val = ConfigParser.SafeConfigParser.getint(self, section, name)
        except:
            val = int(default)
        return val

    def getfloat(self, section, name, default=0.0):
        try:
            val = ConfigParser.SafeConfigParser.getfloat(self, section, name)
        except:
            val = float(default)
        return val

    def getbool(self, section, name, default=False):
        if self.has_option(section, name):
            val = self.get(section, name)
            val = val.lower() == 'true'
        else:
            val = default
        return val

    def setbool(self, section, name, value):
        if value:
            self.set(section, name, 'true')
        else:
            self.set(section, name, 'false')

    def dump(self):
        s = StringIO.StringIO()
        self.write(s)
        print s.getvalue()
