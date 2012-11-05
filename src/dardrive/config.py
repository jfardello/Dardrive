import os
import logging
from ConfigParser import SafeConfigParser, NoOptionError
from utils import check_file
from excepts import *


class Config(object):
    global_section = 'global'

    def __init__(self, file_name, defaults={}):

        #SafeConfigParser defalts will apply to all sections, which actually,
        #sucks. We're going to manually set the defaults for the global_section
        #is unset.
        self.logger = logging.getLogger(__name__)
        file_name = check_file(file_name, InitException)
        self.cp = SafeConfigParser()
        if not self.cp.has_section(self.global_section):
            self.cp.add_section(self.global_section)
        for key in defaults.keys():
            if not self.cp.has_option(self.global_section, key):
                self.cp.set(self.global_section, key, defaults[key][0])

        self.cp.read(os.path.expanduser(file_name))
        self.file_name = file_name
        self._defaults = defaults

    def sync(self):
        with open(os.path.expanduser(self.file_name), 'w') as config:
            self.cp.write(config)

    def add_section(self, section):
        if not self.cp.has_section(section):
            self.cp.add_section(section)

    def sections(self):
        return filter(lambda x: self.global_section != x, self.cp.sections())

    def __getattr__(self, name):
        if name in self.sections():
            return Section(name, self.cp, self._defaults, self.global_section)
        else:
            self.logger.debug(self.sections())
            self.logger.debug(name in self.sections())
            self.logger.debug(name)
            raise ConfigSectionException('Unexistent section %s.' % name)

    def __repr__(self):
        return '<Configuration from %s>' % self.file_name

    def __dir__(self):
        return self.sections()


class Section(object):
    def __init__(self, name, parser, defaults, global_section='global'):
        self.name = name
        self.defaults = defaults
        self.cp = parser
        self.global_section = global_section
        self.log = logging.getLogger(__name__)

    def __getattr__(self, name):

        def __getopts(where, name):
            if name in self.defaults.keys():
                op = self.defaults[name]
                v = op.validator
                #self.log.debug("Looking for %s in %s." % (name, where))
                if op.type is int:
                    if v.__name__ == "validate_noint":
                        return v(name, self.cp.get(where, name), op.type)
                    else:
                        return v(name, self.cp.getint(where, name), op.type)
                elif op.type is bool:
                    return v(name, self.cp.getboolean(where, name), op.type)
                elif op.type is str:
                    return v(name, self.cp.get(where, name), op.type)
            else:
                self.log.debug("%s is not a valid option!" % name)
                raise ConfigValidationException(
                    '%s is not a valid option.' % name)

        try:
            return __getopts(self.name, name)
        except NoOptionError:
            try:
                return __getopts(self.global_section, name)
            except NoOptionError:
                raise AttributeError('%s is not a valid option.' % name)

    def set(self, attr, val):
        try:
            if attr in self.defaults.keys():
                self.log.debug("Assigning  %s value %s to key %s" % (
                    self.defaults[attr][1], val, attr))
                if self.defaults[attr][1] is bool:
                    assert val.lower().strip() in (
                        "yes", "no", "true", "false")
                if self.defaults[attr][1] is int:
                    try:
                        int(val)
                    except ValueError:
                        raise ConfigException('Invalid value for %s' % attr)
                self.cp.set(self.name, attr, val)
        except (AssertionError, ValueError), e:
            _type = self.defaults[attr][1]
            raise ConfigException(
                'atribute %s should be %s, not %s' % (attr, _type, val))

    def options(self):
        return  sorted(list(set(self.cp.options(self.name) + self.cp.options(
            self.global_section))))

    def __repr__(self):
        return '<Configuration section %s>' % self.name

    def __dir__(self):
        return self.options()
