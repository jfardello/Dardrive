# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config


class MockValidators(object):
    '''
    >>> from dardrive.utils import validate_dar_pass 
    >>> from dardrive.utils import validate_nofile
    >>> from dardrive.utils import validate_nostring
    >>> validate_dar_pass('encryption', 'no', str)
    False
    >>> validate_dar_pass('encryption', 'aes:secret', str)
    'aes:secret'
    >>> validate_dar_pass('encryption', 'a3s:secret', str) #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    excepts.ConfigValidationException: Cipher not allowed(a3s)
    >>> validate_nofile('exclude', 'no', str)
    False
    >>> validate_nofile('exclude', 'Off', str)
    False
    >>> validate_nofile('exclude', '/tmp', str)
    '/tmp'
    >>> validate_nostring('email_from', 'bar@foo.com', str)
    'bar@foo.com'
    >>> validate_nostring('email_from', 'Off', str)
    False
    >>> validate_nostring('email_from', 'no', str)
    False
    >>> validate_nostring('email_from', 'On', str) #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last): 
    excepts.ConfigValidationException: "email_from" allows config parser's "no" values or strings, true booleans are not allowed 
    '''
    pass


if __name__ == "__main__":
    import doctest
    doctest.testmod()
