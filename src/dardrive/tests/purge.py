# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config

import os
import sys
sys.path.append(os.path.dirname(__file__))
import darsetts


class TestPurge(object):
    '''
    >>> import os, sys
    >>> from datetime import datetime, timedelta, date
    >>> import dardrive.db as db
    >>> from dardrive.dar import Scheme
    >>> from dardrive.utils import DARDRIVE_DEFAULTS
    >>> from dardrive.config import Config
    >>> days_back = lambda x:datetime.today() - timedelta(days=x)
    >>> fname = os.path.join(os.path.dirname(__file__), "test.cfg")
    >>> cf = Config(fname, DARDRIVE_DEFAULTS)
    >>> s = Scheme(cf, 'test', None, darsetts.engine, False)
    >>> tday = date.today().day
    >>> Inc = s.Incremental
    >>> Full = s.Full
    >>> last_year = datetime.today().year - 1
    >>> s.sess.add(db.Catalog(job=s.Job, date=datetime(last_year -1, 11, 27), type=Full))
    >>> s.sess.add(db.Catalog(job=s.Job, date=datetime(last_year -1, 12, 27), type=Full))
    >>> s.sess.add(db.Catalog(job=s.Job, date=datetime(last_year, 12, 31), type=Full))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(100 + tday), type=Full))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(80 + tday), type=Full))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(4), type=s.Full))
    >>> s.sess.commit()
    >>> first = s.sess.query(db.Catalog).order_by(db.Catalog.date).first()
    >>> last = s.sess.query(db.Catalog).order_by(db.Catalog.date.desc()).first()
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(49), type=Inc, parent=first))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(48), type=Inc, parent=first))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(3), type=Inc, parent=last))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(2), type=Inc, parent=last))
    >>> s.sess.add(db.Catalog(job=s.Job, date=days_back(1), type=Inc, parent=last))
    >>> s.sess.commit()
    >>> s.sess.query(db.Catalog).update({db.Catalog.clean:1})
    11
    >>> s.sess.commit()
    >>> s.promote(s.Full)
    >>> s.sess.query(db.Catalog).filter(db.Catalog.hierarchy == 1).count()
    4
    >>> s.sess.query(db.Catalog).filter(db.Catalog.hierarchy == 2).count()
    3
    >>>
    '''
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
