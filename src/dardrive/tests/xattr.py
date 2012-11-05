# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config

import os
import sys
sys.path.append(os.path.dirname(__file__))
import darsetts


import os
def touch(fname, times=None):
    if not os.path.exists(os.path.dirname(fname)):
        os.makedirs(os.path.dirname(fname))
    with file(fname, 'a'):
        os.utime(fname, times)


class TestImporter(object):
    '''
    >>> import os, sys
    >>> from datetime import datetime, timedelta, date
    >>> from sqlalchemy.orm import sessionmaker
    >>> from sqlalchemy import func
    >>> from sqlalchemy import create_engine
    >>> from dardrive.db import *
    >>> from dardrive.dar import Scheme
    >>> from dardrive.utils import DARDRIVE_DEFAULTS, save_xattr
    >>> from dardrive.config import Config
    >>> days_back = lambda x:datetime.today() - timedelta(days=x)
    >>> create_all(darsetts.engine)
    >>> days_back = lambda x:datetime.today() - timedelta(days=x)
    >>> fname = os.path.join(os.path.dirname(__file__), "test.cfg")
    >>> conf = Config(fname, DARDRIVE_DEFAULTS)
    >>> cf = conf.test
    >>> s = Scheme(conf, 'test', None, darsetts.engine, False)
    >>> dontcare = s.sess.query(Catalog).delete()
    >>> s.sess.commit()
    >>> cat1 = Catalog(job=s.Job, date=days_back(10), type=s.Full)
    >>> cat2 = Catalog(job=s.Job, date=days_back(20), type=s.Full)
    >>> cat1.ttook = 10
    >>> cat1.status = 0
    >>> cat1.clean = False
    >>> cat2.ttook = 20
    >>> cat2.status = 0
    >>> cat2.clean = True
    >>> s.sess.add(cat1)
    >>> s.sess.add(cat2)
    >>> s.sess.commit()
    >>> cat3 = Catalog(job=s.Job, date=days_back(1), type=s.Incremental, parent=cat2)
    >>> cat3.ttook = 30
    >>> cat3.status = 0
    >>> cat3.clean = True
    >>> s.sess.add(cat3)
    >>> s.sess.commit()
    >>> touch(os.path.join(cf.archive_store,"test", cat1.id + ".1.dar"))
    >>> touch(os.path.join(cf.archive_store,"test", cat2.id + ".1.dar"))
    >>> touch(os.path.join(cf.archive_store,"test", cat3.id + ".1.dar"))
    >>> save_xattr(cat1, cf)
    >>> save_xattr(cat2, cf)
    >>> save_xattr(cat3, cf)
    >>> dontcare = s.sess.query(Catalog).delete()
    >>> s.sess.commit()
    >>> i = Importer(conf, 'test', s.sess)
    >>> i.load()
    '''
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
