# -*- coding: iso-8859-15 -*-
# 2011, José Manuel Fardello <jfardello@uoc.edu>
# Doctest for dardrive config

import os
import sys
sys.path.append(os.path.dirname(__file__))
import darsetts


class Stat(object):
    '''
    >>> import os, sys
    >>> from datetime import datetime, timedelta
    >>> from sqlalchemy import func
    >>> from sqlalchemy import create_engine
    >>> from dardrive.db import *
    >>> from dardrive.db import save_stats
    >>> from sqlalchemy.orm import relationship, sessionmaker
    >>> create_all(darsetts.engine)
    >>> Sess = sessionmaker(bind=darsetts.engine)
    >>> s = Sess(bind=darsetts.engine)
    >>> r = Report("test", session=s)
    >>> job = s.query(Job).filter(Job.name == "test").one()
    >>> full = s.query(BackupType).get(1)
    >>> inc = s.query(BackupType).get(2)
    >>> cat1 = Catalog(job=job, type=full)
    >>> cat2 = Catalog(job=job, type=inc)
    >>> cat3 = Catalog(job=job, type=inc)
    >>> cat1.ttook = 100
    >>> cat2.ttook = 50
    >>> cat3.ttook = 60
    >>> cat1.status = 0
    >>> cat2.status = 0
    >>> cat3.status = 0
    >>> s.add_all([cat1, cat2, cat3])
    >>> s.commit()
    >>> save_stats(cat1, s)
    >>> save_stats(cat2, s)
    >>> save_stats(cat3, s)
    >>> r.avg()
    datetime.timedelta(0, 70)
    >>> r.avg(backup_type=inc)
    datetime.timedelta(0, 55)
    >>>
    '''
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
