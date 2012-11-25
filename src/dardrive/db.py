from __future__ import print_function
import os
import sys
import uuid
import logging
import glob
import copy
from socket import gethostname
from datetime import datetime
from datetime import timedelta

import xattr
from sqlalchemy import func, or_, create_engine, ForeignKey, Column
from sqlalchemy import DateTime, Integer, SmallInteger, String, Boolean
from sqlalchemy.sql import ClauseElement
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import UniqueConstraint
from config import Config
from utils import mkdir, DARDRIVE_DEFAULTS
from excepts import *

sys.path.append(os.path.expanduser("~/.dardrive"))
try:
    from setts import engine
    from setts import CONFIGFILE
except ImportError:
    engine = create_engine('sqlite:///:memory:', echo=False)
    CONFIGFILE = "~/.dardrive/jobs.cfg"


Base = declarative_base()

__all__ = ["Catalog", "BackupType", "Job", "engine", "create_all", "Report",
           "Importer", "find_ext"]

dardrive_types = (
    ("Incremental", "dar"),
    ("Full", "dar"),
    ("MysqlDump", "dmp"),
    ("gzMysqlDump", "dmp.gz")
)
mkid = lambda: uuid.uuid4().hex


def find_ext(btype):
    for name, ext in dardrive_types:
        if btype == name:
            return ext
    raise Exception("Extension not found.")

class Stat(Base):
    __tablename__ = "stats"
    id = Column(String, primary_key=True, default=mkid)
    job_id = Column(String, ForeignKey('jobs.id'))
    job = relationship("Job")
    type_id = Column(String, ForeignKey('types.id'))
    type = relationship("BackupType")
    date = Column(DateTime, default=datetime.now)
    ttook = Column(Integer, nullable=True)



class Catalog(Base):
    __tablename__ = "catalogs"

    id = Column(String, primary_key=True, default=mkid)
    job_id = Column(String, ForeignKey('jobs.id'))
    job = relationship("Job")
    type_id = Column(String, ForeignKey('types.id'))
    type = relationship("BackupType")
    enc = Column(Boolean, default=False)
    comment = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.now)
    parent_id = Column(Integer, ForeignKey('catalogs.id'))
    parent = relationship("Catalog", remote_side=[id], backref="child")
    clean = Column(Boolean, default=False)
    hierarchy = Column(SmallInteger, default=1)
    status = Column(SmallInteger, nullable=True)
    ttook = Column(Integer, nullable=True)
    log = Column(String, nullable=True)

    def __init__(self, **kw):
        for k in kw.keys():
            setattr(self, k, kw[k])

    def promote(self, cf):
        self.hierarchy += 1
        store = os.path.join(cf.archive_store, self.job.name, self.id)
        fname = "%s.1.%s" % (store, find_ext(self.type.name))
        if os.path.exists(fname):
            x = xattr.xattr(fname)
            x['user.dardrive.hierarchy'] = str(self.hierarchy)

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.id)

class BackupType(Base):
    __tablename__ = "types"
    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True)

    def __init__(self, **kw):
        for k in kw.keys():
            setattr(self, k, kw[k])

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.name)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True)

    def __init__(self, **kw):
        for k in kw.keys():
            setattr(self, k, kw[k])

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.name)


class Lock(Base):
    '''Rudimentary multi host pid-locking.'''
    __tablename__ = "locks"
    id = Column(String, primary_key=True, default=mkid)
    hname = Column(String(32))
    oper = Column(String(32))
    job_id = Column(String, ForeignKey('jobs.id'))
    job = relationship("Job")
    cat_id = Column(String, ForeignKey('catalogs.id'))
    cat = relationship("Catalog")
    locktime = Column(DateTime, default=datetime.now)
    pid = Column(Integer)
    __table_args__ = (UniqueConstraint('hname', 'oper', 'job_id',
                                       name='_uq_hname_oper_job'),)

    def __init__(self, job, oper, cat=None):
        self.job = job
        self.oper = oper
        self.hname = gethostname()
        self.pid = os.getpid()
        if cat:
            self.cat = cat

    def check_pid(self):
        """ Check for the existence of a unix pid. """
        try:
            os.kill(self.pid, 0)
        except OSError:
            return False
        else:
            return True

    def __repr__(self):
        return "<%s:%s_%s>" % (self.__class__.__name__,
                               self.job.name, self.oper)


def create_all(e):
    Base.metadata.create_all(e)


def get_or_create(model, sess, **kwargs):
    logger = logging.getLogger(__name__)
    instance = sess.query(model).filter_by(**kwargs).first()
    if instance:
        logger.debug("got: %s" % instance)
        return instance
    else:
        params = dict((k, v) for k, v in kwargs.iteritems(
        ) if not isinstance(v, ClauseElement))
        instance = model(**params)
        sess.add(instance)
        sess.commit()
        logger.debug("created: %s" % instance)
    return instance

def save_stats(ins, s):
    '''Saves time statistics.'''
    logger = logging.getLogger("db.save_stats")
    #dar successfull codes, see dar(1)
    if ins.status in [0, 11]:
        with s.begin(subtransactions=True):
            c = s.query(Stat).filter_by(id=ins.id).first()
            if not c:
                c = Stat(id=ins.id, job=ins.job, type=ins.type,
                    date=ins.date, ttook=ins.ttook)
                s.add(c)
                logger.debug("Stats saved for %s" % c.id)


class Importer(object):
    '''Bulk imports an archive store into db.'''

    def __init__(self, cf, section, session=None):
        self.logger = logging.getLogger(__name__)
        if session:
            self.s = session
        else:
            create_all(engine)
            Sess = sessionmaker(bind=engine)
            self.s = Sess(bind=engine)

        try:
            self.cf = getattr(cf, section)
        except ConfigException, e:
            raise ImporterException("There's no %s section in the "
                                    "congiguration" % section)

        self.job = get_or_create(Job, self.s, name=section)
        self.path = os.path.join(self.cf.archive_store, section)
        for btype, ext in dardrive_types:
            setattr(self, btype, get_or_create(BackupType, self.s, name=btype))
        self.s.commit()

    def load(self):
        files = []
        for btype, ext in dardrive_types:
            self.logger.debug("Looking for %s/*.1.%s" %
                              (self.path.rstrip("/"), ext))

            files += glob.glob("%s/*.1.%s" % (self.path, ext))

        parents = {}
        for imported in files:
            self.logger.debug("Trying to load for %s" % imported)

            #we're gonna work with a copy of the attrs.
            _imp = dict(xattr.xattr(imported))
            job_id = os.path.basename(imported).split(".")[0]
            #save the parent info.
            if _imp['user.dardrive.parent'] != "":
                parents[job_id] = _imp['user.dardrive.parent']

            if len(_imp.keys()) < 1:
                self.logger.debug("couldn't load extended attributes for %s" %
                                  imported)
                continue
            #allow Null values:
            for key in _imp.keys():
                if _imp[key] == "":
                    _imp[key] = None

            _imp['user.dardrive.date'] = datetime.strptime(
                _imp['user.dardrive.date'], "%Y-%m-%d %H:%M:%S.%f")

            if _imp['user.dardrive.job'] != self.job.name:
                self.logger.debug("job xattr differs from current job: %s" %
                                  self.job.name)
                continue
            cat = get_or_create(Catalog, self.s,
                                id=job_id,
                                type=getattr(self, _imp['user.dardrive.type']),
                                job=self.job,
                                comment=_imp['user.dardrive.comment'],
                                clean=(_imp['user.dardrive.clean'] == "True"),
                                hierarchy = int(
                                    _imp['user.dardrive.hierarchy']),
                                status = int(_imp['user.dardrive.status']),
                                date = _imp['user.dardrive.date'],
                                enc = (_imp['user.dardrive.enc'] == "True"),
                                ttook = int(_imp['user.dardrive.ttook'])
                                )
            self.s.commit()

        for child in parents.keys():
            _c = get_or_create(Catalog, self.s, id=child)
            _p = get_or_create(Catalog, self.s, id=parents[child])
            _c.parent = _p
        self.s.commit()


class Report(object):
    '''Wraps some common operations on catalogs ans jobs, like average time,
    or accessing to the logs'''

    job = None

    def __init__(self, job_name, session=None):
        self.logger = logging.getLogger(__name__)
        if session:
            self.s = session
        else:
            create_all(engine)
            Sess = sessionmaker(bind=engine)
            self.s = Sess(bind=engine)

        if job_name:
            try:
                self.job = self.s.query(Job).filter(Job.name == job_name).one()
            except NoResultFound:
                cf = Config(CONFIGFILE, DARDRIVE_DEFAULTS)
                if job_name in cf.sections():
                    self.job = get_or_create(Job, self.s, name=job_name)
                else:
                    raise ConfigSectionException(
                        "No such section: %s" % job_name)

    def type(self, t):
        try:
            if isinstance(t, BackupType):
                return t
            else:
                return self.s.query(BackupType).filter(BackupType.name == t)\
                    .one()
        except NoResultFound:
            return None

    def types(self):
        types = self.s.query(BackupType.name).all()
        return map(lambda x: x[0], types)

    def avg(self, backup_type=None):
        '''Returns the average time in seconds for a given job and job type
        (if any)'''
        avg = self.s.query(func.avg(Stat.ttook))
        if self.job:
            avg = avg.filter(Stat.job == self.job)
        if backup_type:
            avg = avg.filter(Stat.type == self.type(backup_type))

        avg = avg.one()
        if avg[0]:
            return timedelta(seconds=int(avg[0]))
        else:
            return "No data."

    def last_run(self, backup_type=None):
        '''Returns the time in seconds for the last run of a given job and job
        type(if any)'''

        l = self.s.query(Stat.ttook)
        if self.job:
            l = l.filter(Stat.job == self.job)
        if backup_type:
            l = l.filter(Stat.type == self.type(backup_type))

        l = l.order_by(Stat.date.desc()).first()
        if l:
            return timedelta(seconds=l[0])
        else:
            return "No data"

    def get_catalogs(self, catalog=None, order="desc", types=None, after=None,
                     entries=0):
        '''Returns a queryset matching the arguments'''

        l = self.s.query(Catalog)
        if catalog:
            return l.filter(Catalog.id == catalog)
        else:
            if after:
                l = l.filter(Catalog.date >= after)
            if self.job:
                l = l.filter(Catalog.job == self.job)
            if types:
                clauses = []
                for backup_type in types:
                    clauses.append(Catalog.type == self.type(backup_type))
                l = l.filter(or_(*clauses))
            if order == "desc":
                l = l.order_by(Catalog.date.desc())
            else:
                l = l.order_by(Catalog.date)
            if entries > 0:
                l = l.limit(entries)
            return l
