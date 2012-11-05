# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config


class TestConfig(object):
    '''
    >>> import ConfigParser, tempfile, os
    >>> from dardrive.config import Config
    >>> from dardrive.utils import Op
    >>> handle, fname = tempfile.mkstemp()
    >>> config = ConfigParser.RawConfigParser()
    >>> config.add_section('global')
    >>> config.set('global', 'int', '15')
    >>> config.set('global', 'bool', 'yes')
    >>> config.set('global', 'str', 'hey')
    >>> config.add_section('test')
    >>> config.set('global', 'int', '2')
    >>> with open(fname, 'wb') as configfile:
    ...     config.write(configfile)
    >>>
    >>> cf = Config(fname, {'default':Op('default', str),'int':Op('22',int),'bool':Op('yes',bool),'str':Op('abcde',str)})
    >>> cf.test
    <Configuration section test>
    >>> cf.test.default
    'default'
    >>> assert cf.test.bool is True
    >>> assert cf.test.int is 2
    >>> cf.test.lololol  #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ConfigValidationException: lololol is not a valid option.
    >>> cf.test.options()
    ['bool', 'default', 'int', 'str']
    >>> cf.sections()
    ['test']
    >>> del cf
    >>> os.remove(fname)
    >>>
    '''
    pass


if __name__ == "__main__":
    import doctest
    doctest.testmod()
