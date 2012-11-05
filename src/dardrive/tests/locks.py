# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config

import os
import sys
sys.path.append(os.path.dirname(__file__))
import darsetts


class TestLocks(object):
    '''
    >>> import os, sys
    >>> from dardrive.dar import Scheme
    >>> from dardrive.utils import DARDRIVE_DEFAULTS 
    >>> from dardrive.config import Config
    >>> fname = os.path.join(os.path.dirname(__file__), "test.cfg")
    >>> conf = Config(fname, DARDRIVE_DEFAULTS)
    >>> s = Scheme(conf, 'test', None, darsetts.engine, False)
    >>> l = s.lock("gabbagabbahey")
    >>> l
    <Lock:test_gabbagabbahey>
    >>> s.lock("gabbagabbahey")
    False
    >>> s.sess.delete(l)
    >>> s.sess.commit()
    >>> 
    '''
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
