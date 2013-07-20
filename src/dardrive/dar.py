#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#2012, jfardello@uoc.edu

from __future__ import print_function

import os
import sys
import imp
import datetime
import time
import glob
import re
import logging
import argparse
import shlex
import subprocess
import shutil
from collections import namedtuple
from itertools import groupby

from sqlalchemy.sql import and_, exists
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import InvalidRequestError

from config import Config
from db import Catalog, Stat, BackupType, Job, engine, create_all, Lock
from db import get_or_create, dardrive_types, find_ext, Report, save_stats
from excepts import *
from utils import mkdir, userconfig, DARDRIVE_DEFAULTS, check_file
from utils import mk_mysql_auth_file, ordinal, parsedar_dates
from utils import mk_ssl_auth_file
from utils import is_admin, save_xattr, mk_dar_crypt_file


setts_file = os.path.expanduser('~/.dardrive/setts.py')
if os.path.exists(setts_file):
    setts = imp.load_source('setts', setts_file)
else:
    Setts = namedtuple('Setts', ['engine'])
    db = os.path.expanduser('~/.dardrive/dardrive.db')
    setts = Setts(engine="sqlite:///%s" % db)


def getchilds(elem):
    if len(elem.child) > 0:
        return elem.child + getchilds(elem.child[0])
    else:
        return []


def getancestors(elem):
    if elem.parent:
        return [elem.parent] + getancestors(elem.parent)
    else:
        return []


class DateShift(object):
    SHIFT = 0

    def today(self):
        return datetime.datetime.today() + datetime.timedelta(
            days=self.SHIFT)

    def shift(self, days):
        self.SHIFT += days

commands = {
    'full_bck': '%(dar_bin)s -c %(basename)s -@%(catalog)s -R %(path)s -Q ',
    'inc_bck': '%(dar_bin)s -c %(basename)s -A %(refcatalog)s -Q '
    '-@%(catalog)s -R %(path)s ',
    'popen_defaults': {
        'stdin': subprocess.PIPE,
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE}
}

bakup_extra = {
    'par': ' -E "dar_par_create.duc %%p %%b %%N %%e %%c %(redundancy)s"',
    'par_local': ' -E "dardrive_move -j %(jobname)s -i %%b -s %%n"',
    'compr': ' --compression=%(compr)s:%(compr_level)i',
    'compr_min': ' -m%(compr_min)i',
    'compr_exempt': ' -ar -Z %(compr_exempt)s',
    'encryption': ' -B %(encryption)s',
    'slice': ' -s %(slice)s',
    'same_fs': ' -M',
    'exclude_regex': ' -ar --exclude %(exclude_regex)s',
    'exclude_file': ' --exclude-from-file %(exclude_file)s'
}


class Scheme(object):
    '''Chooses whether or not to do an incremental backup, and also determines
    the retention policy.  This is a base class that implements a
    grandfather-father-son backup scheme, in order to implement a better scheme
    you should subclass and override choose() and promote() methods.'''

    args = {}

    def __init__(self, config, section, root=None, engine=None, dmd=True):

        #a mock-friendly datetime
        self.dt = DateShift()

        if section not in config.sections():
            raise ConfigException('There is not such job')

        self.logger = logging.getLogger(__name__)
        if engine is None:
            engine = setts.engine
        self.cf = getattr(config, section)
        self.section = section
        self.args['jobname'] = section

        check_file(self.cf.dar_bin, ConfigException)

        if root is not None:
            self.args['path'] = root
        else:
            self.args['path'] = self.cf.root

        for opt in self.cf.options():
            self.args[opt] = getattr(self.cf, opt)

        create_all(engine)
        Sess = sessionmaker(bind=engine)
        self.sess = Sess(bind=engine)

        #init dardrive backup types
        for btype, ext in dardrive_types:
            setattr(self, btype, self.get_or_create(BackupType, name=btype))
        for each_section in config.sections():
            self.get_or_create(Job, name=each_section)

        self.sess.commit()

        self.Job = self.get_or_create(Job, name=section)

        self.dmd = os.path.expanduser('~/.dardrive/dmd/%s.dmd' % section)

        if not os.path.exists(self.dmd) and dmd:
            args = {'dar_manager': self.cf.dar_manager_bin,
                    'dmd_file': self.dmd}
            run = self.run_command('%(dar_manager)s -C %(dmd_file)s', args)
            if run[0].returncode > 0:
                raise BackupException

    def save_stats(self, ins):
        save_stats(ins, self.sess)

    def get_or_create(self, model, **kwargs):
        return get_or_create(model, self.sess, **kwargs)

    def get_last(self, full=False):
        '''Returns the days since last diff-backup or full-backup'''
        if self.sess.query(Catalog).count() > 0:
            if full:
                last = self.sess.query(Catalog).filter(
                    and_(Catalog.type == self.Full,
                         Catalog.job == self.Job,
                         Catalog.clean)).order_by(Catalog.date.desc()).first()
            else:
                last = self.sess.query(Catalog).filter(
                    and_(Catalog.clean,
                         Catalog.job == self.Job)).order_by(
                             Catalog.date.desc()).first()

            if last is None:
                return None
            else:
                t = self.dt.today()
                return (t - last.date).days
        else:
            return None

    def choose(self, force_full):
        '''Creates and returns a catalog for the default bachup scheme.'''

        lastfull = self.get_last(full=True)
        if lastfull is None or (lastfull > self.cf.diffdays) or force_full:
            cat = Catalog(type=self.Full, job=self.Job)
            self.logger.debug("chose a full backup:")
            self.logger.debug("  lastfull is %s" % lastfull)
            self.logger.debug("  diffdays is %s" % self.cf.diffdays)
            self.logger.debug("  force_full is %s" % force_full)
        else:
            cond = and_(Catalog.clean, Catalog.job == self.Job,
                        Catalog.type_id.in_([1, 2]))
            ref = self.sess.query(Catalog).filter(cond)
            self.refbasename = ref.order_by(Catalog.date.desc()).first()
            if self.refbasename is None:
                raise CatalogException("Can't find the previous catalog!")
            cat = Catalog(type=self.Incremental, job=self.Job,
                          parent=self.refbasename)
            self.logger.debug("chose an incremental  backup")

        self.sess.add(cat)

        return cat

    def promote(self, btype):
        '''Backup rotation'''
        #First generation, promote to monthly archive
        td = self.dt.today()
        stop = td - datetime.timedelta(days=30)  # TODO: mk an option for this

        crit = and_(Catalog.date < stop, Catalog.clean == True,
                    Catalog.type == btype, Catalog.hierarchy == 1)

        s = self.sess.query(
            Catalog).filter(crit).order_by(Catalog.date.desc()).all()
        for each in groupby(s, lambda x: x.date.year * 100 + x.date.month):
            month, catalogs = each
            self.logger.debug('Promoting for month %s:' % month)
            self.promote_for(catalogs, 1)

        #If btype is Full, get incremental backups prior to the last Full and
        #delete them.
        if btype is self.Full:
            l = self.sess.query(Catalog).filter(and_(
                Catalog.type == self.Full,
                Catalog.job == self.Job,
                Catalog.hierarchy == 1,
                Catalog.clean == True))
            l = l.order_by(Catalog.date.desc()).first()

            if l:
                s = self.sess.query(Catalog).filter(and_(
                    Catalog.date < l.date,
                    Catalog.type == self.Incremental,
                    Catalog.hierarchy == 1,
                    Catalog.clean == True)).all()
                for oinc in s:
                    msg = "Deleting from %s %s generation archive %s"
                    msg += " (useless incremental)"
                    self.logger.debug(msg % ("fs",
                                             ordinal(oinc.hierarchy), oinc.id))
                    self.fs_remove(oinc.id)
                    self.logger.debug(msg % ("db",
                                             ordinal(oinc.hierarchy), oinc.id))
                    self.sess.delete(oinc)
                self.sess.commit()

        #Second generation, promote to yearly archive

        #get all monthly archives older than a year
        am = self.sess.query(Catalog)
        am = am.filter(and_(
            Catalog.type == btype,
            Catalog.hierarchy == 2,
            Catalog.date < td - datetime.timedelta(days=365)))
        am = am.order_by(Catalog.date.desc()).all()

        for each in groupby(am, lambda x: x.date.year):
            year, catalogs = each
            self.logger.debug('Promoting for year %s:' % year)
            self.promote_for(catalogs, 2)

    def promote_for(self, catalogs, hierarchy):
        '''See if we can find a catalog (promoted or not), in the same period
        (month or year), newer than the first element in catalogs. If it
        exists promote it (if not already promoted), then delete all the other
        catalogs that are older than the maximum age allowed for that
        generation. If there's no candidate for the promotion promote the first
        element in catalogs, which it should be our best choice: the oldest
        known catalog in a period of time, as the catalogs are ordered and all
        of them belongs to the same period.'''
        catalogs = list(catalogs)
        cat = catalogs[0]
        del_extra = []

        #The period will vary depending on the generation.
        if hierarchy == 1:
            #month overload
            if cat.date.month == 12:
                period = datetime.date(cat.date.year + 1, 1, 1)
            else:
                period = datetime.date(cat.date.year, cat.date.month + 1, 1)
            del_cond = self.dt.today() - datetime.timedelta(days=30)
        elif hierarchy == 2:
            period = datetime.date(cat.date.year + 1, 1, 1)
            del_cond = self.dt.today() - datetime.timedelta(days=365)
        else:
            raise RuntimeError("promote_for is not smart enough for this"
                               " operation.")
        s = self.sess.query(Catalog).filter(
            and_(Catalog.date < period,
                 Catalog.date > cat.date,
                 Catalog.hierarchy >= cat.hierarchy,
                 Catalog.type == self.Full,
                 Catalog.job == self.Job)).order_by(Catalog.date.desc())
        if s.count() > 0:
            del_extra = [cat]
            new_cat = s.first()
            if new_cat.hierarchy == hierarchy:
                self.logger.debug("Promoting %s to %s generation archive"
                                  % (new_cat.id,
                                     ordinal(new_cat.hierarchy + 1)))
                new_cat.promote(self.cf)
        else:
            self.logger.debug("Promoting %s to %s generation archive"
                              % (cat.id, cat.hierarchy + 1))
            cat.promote(self.cf)
        for each in catalogs[1:] + del_extra:
            if each.date < del_cond:
                msg = "Deleting from fs %s generation archive %s"
                self.logger.debug(msg % (ordinal(each.hierarchy), each.id))
                self.fs_remove(each.id)
                msg = "Deleting from db %s generation archive %s"
                self.logger.debug(msg % (ordinal(each.hierarchy), each.id))
                self.sess.delete(each)
        self.sess.commit()

    def fs_remove(self, basename):
        def delete_file(file_name):
            if os.path.isfile(file_name):
                os.remove(file_name)

        self.logger.debug("fs_remove called with for %s" % basename)
        archives_p = os.path.join(
            self.cf.archive_store, self.Job.name, basename)
        archives = glob.glob("%s.*.dar" % archives_p)
        archives += glob.glob("%s.*.dar.par2" % archives_p)
        archives += glob.glob("%s.*.dar.vol*.par2" % archives_p)
        archives += glob.glob("%s.*.dmp" % archives_p)
        archives += glob.glob("%s.*.dmp.par2" % archives_p)
        archives += glob.glob("%s.*.dmp.vol*.par2" % archives_p)
        archives += glob.glob("%s.*.dmp.gz" % archives_p)
        archives += glob.glob("%s.*.dmp.gz.par2" % archives_p)
        archives += glob.glob("%s.*.dmp.gz.vol*.par2" % archives_p)

        #This is kinda weird, if you slice a catalog so freaking small you'll
        #end up with a multivolume catalog, which is a very silly thing.
        catalogs = os.path.join(
            self.cf.catalog_store, self.Job.name, basename)
        catalogs = glob.glob("%s.*.dar" % catalogs)

        if len(archives) > 0:
            map(lambda x: delete_file(x), archives)

        if len(catalogs) > 0:
            map(lambda x: delete_file(x), catalogs)

        dmds = self.load_dmd()
        if  basename in dmds.keys():
            #Delete from dmd
            dmd = dmds[basename]
            tpl = "%(dar_manager)s -B %(dmd_file)s -D %(id)s"
            args = {'id': dmd.num, 'dar_manager': self.cf.dar_manager_bin,
                    'dmd_file': self.dmd}
            self.logger.debug('Deleting archive from dmd.')
            run = self.run_command(tpl, args)

    def lock(self, oper, cat=None):
        try:
            lock = Lock(self.Job, oper, cat)
            self.sess.add(lock)
            self.logger.debug("Locking on job:%s, oper:%s, pid:%s" %
                              (lock.job.name, lock.oper, lock.pid))
            self.sess.commit()
            return lock
        except:
            self.sess.rollback()
            self.logger.debug("Lock rolled back!!")
            oldlock = self.sess.query(Lock).filter(
                Lock.job == self.Job,
                Lock.oper == oper).one()
            if oldlock.check_pid():
                if os.getpid() == oldlock.pid:
                    #It semms you locked twice!
                    self.logger.debug("Hey! you locked twice!!")
                    return False
                else:
                    raise LockException(
                        "Another instance (pid %s) is still "
                        "running this job's %s " % (oldlock.pid, oper))
            else:
                self.logger.debug("Removing old lock on %s." % oper)
                self.sess.delete(oldlock)
                self.sess.commit()
                return self.lock(oper, cat)

    def db_backup(self):
        if not self.cf.mysql:
            raise ConfigException('MySQL dumps are not enabled '
                                  'for this job.\n')
        lock = self.lock("db_backup")

        mpath = os.path.join(self.cf.archive_store, self.section)
        mkdir(mpath)
        if self.cf.mysql_compr:
            btype_name = "gzMysqlDump"
            ext = ".dmp.gz"
        else:
            btype_name = "MysqlDump"
            ext = ".dmp"
        btype = self.get_or_create(BackupType, name=btype_name)
        cat = Catalog(type=btype, job=self.Job)
        self.sess.add(cat)
        lock.cat = cat
        self.sess.add(lock)
        self.sess.commit()
        # we use a slice naming convention as in dar, in a future, it would
        #be nice to be able to split dump files.

        file_name = os.path.join(mpath, cat.id + ".1" + ext)

        if self.cf.redundancy and self.cf.par_local:
            dest_file_name = file_name
            file_name = os.path.join(self.cf.local_store, self.section,
                                     cat.id + ".1" + ext)

        args = "mysqldump --defaults-extra-file=%s --single-transaction "
        args += "--all-databases -e --opt "

        #mk_mysql_auth_file will create the config for the job
        auth_file = mk_mysql_auth_file(
            id=cat.id.encode(),
            mysql_host=self.cf.mysql_host,
            mysql_user=self.cf.mysql_user,
            mysql_pass=self.cf.mysql_pass)
        self.logger.debug("Mysql authfile created: %s" % auth_file)

        args = shlex.split(args % auth_file)
        testcmd = 'echo status | mysql --defaults-extra-file=%s' % auth_file
        try:
            t = subprocess.check_call(testcmd, shell=True,
                                      **commands['popen_defaults'])
        except subprocess.CalledProcessError:
            self.logger.debug('Deleting auth_file %s' % auth_file)
            os.unlink(auth_file)
            raise BackupDBException('Could not contact the mysql server, check'
                                    ' your configuration/connectivity.\n')
        _dir_name = os.path.dirname(file_name)
        if not os.path.exists(_dir_name):
            os.makedirs(_dir_name, 0722)
        fd = os.open(file_name, os.O_WRONLY | os.O_CREAT, 0600)
        with os.fdopen(fd, 'w') as dmpfile:
            if self.cf.mysql_compr:
                cmdline = " ".join(args) + " | gzip - "
                if self.cf.encryption:
                    pfile = mk_ssl_auth_file(self.cf.encryption.split(":")[1])
                    cmdline += '| openssl aes-256-cbc -salt -pass file:%s' \
                        % pfile
                    cat.enc = True
            elif self.cf.encryption:
                pfile = mk_ssl_auth_file(self.cf.encryption.split(":")[1])
                cmdline = " ".join(args) + \
                    ' | openssl aes-256-cbc -salt  -pass file:%s ' % pfile
                cat.enc = True
            else:
                cmdline = " ".join(args)
                self.logger.debug(cmdline)

            self.logger.debug(cmdline)
            p = subprocess.Popen(
                cmdline, stdin=None, stderr=subprocess.PIPE,
                stdout=dmpfile, shell=True)

            start_time = time.time()
            comm = p.communicate()
            end_time = time.time()

            cat.ttook = int(end_time - start_time)
            cat.log = "stdout:\n%s\nstderr:\n%s\n" % comm
            self.sess.commit()

            if p.returncode == 0:
                if self.cf.redundancy:
                    if self.cf.par_local:
                        store = self.cf.local_store
                    else:
                        store = self.cf.archive_store
                    fpath = str(
                        "%s/%s" % (store, cat.job.name))
                    dar_par(mode="Creating",
                            cmd=[fpath, cat.id.encode(), '1',
                                 ext[1:], '', str(self.cf.redundancy)])
                    if self.cf.par_local:
                        dar_move(
                            cmd=["-j", self.section, "-i", cat.id.encode(),
                                 "-s", "1"], sect=self.cf)

                self.save_stats(cat)
                cat.clean = True

            cat.status = p.returncode
            dmpfile.flush()
            save_xattr(cat, self.cf)
            self.sess.commit()

        self.logger.debug("Deleting authfile %s.." % auth_file)
        os.unlink(auth_file)
        if self.cf.encryption:
            if os.path.exists(pfile):
                os.unlink(pfile)

        self.sess.delete(lock)
        self.sess.commit()
        return cat

    def run_command(self, command, namedargs):
        if command in commands:
            args = commands[command] % namedargs
        else:
            args = command % namedargs

        self.logger.debug(sys.getfilesystemencoding())
        args = shlex.split(args.encode(sys.getfilesystemencoding()))
        self.logger.debug(args)

        command = subprocess.Popen(args, **commands['popen_defaults'])
        start_time = time.time()
        result = command.communicate()
        end_time = time.time()
        self.logger.debug('Command retcode was %i' % command.returncode)
        secs = int(end_time - start_time)
        self.logger.debug('Command completed in %s' % datetime.timedelta(
            seconds=secs))
        return (command, result, secs)

    def run(self, force_full=False):
        '''Create a backup and an isolated catalog, commit the isolated
        catalog to the DMD database, and then point the dmd archive to the
        real backup archive.'''
        if os.path.samefile(self.cf.archive_store, self.cf.catalog_store):
            raise ConfigException("archive_store and catalog_store must be"
                                  " different directories.")

        self.logger.debug("About to create a catalog..")
        self.newcatalog = self.choose(force_full)
        try:
            lock = self.lock("fs_backup", cat=self.newcatalog)
        except LockException, e:
            self.sess.rollback()
            raise e

        self.basename = self.newcatalog.id
        mkdir(self.cf.archive_store, self.section)
        mkdir(self.cf.catalog_store, self.section)
        tpl = self.mk_bkp_args(self.basename)
        run = self.run_command(tpl, self.args)
        self.newcatalog.status = run[0].returncode
        self.newcatalog.log = "stdout: %s\nstderr:%s\n" % run[1]
        self.newcatalog.ttook = run[2]
        self.logger.debug("run: ttook is: %s" % self.newcatalog.ttook)
        self.sess.delete(lock)
        self.sess.commit()
        if run[0].returncode in [0, 5, 11]:
            self.newcatalog.clean = True
            self.sess.commit()
            self.save_stats(self.newcatalog)
            #the xattributes hold data needed when importing an archive store
            #into db.
            save_xattr(self.newcatalog, self.cf)
            self.promote(self.Full)
            self.add_to_dmd(self.newcatalog.id)
        #clean up encryption pass file if present
        if self.cf.encryption and os.path.exists(self.args['encryption']):
            self.logger.debug("Removing encryption command file: %s" %
                              self.args['encryption'])
            os.unlink(self.args['encryption'])

    def add_to_dmd(self, catalog_id):
        catalog_path = os.path.join(self.cf.catalog_store, self.section,
                                    catalog_id)
        archive_path = os.path.join(self.cf.archive_store, self.section,
                                    catalog_id)
        #pass on non dar bkps..
        try:
            ck = check_file(catalog_path + ".1.dar")
            self.logger.debug('Updating the recovery catalog.')
            ctpl = "%(dar_manager)s -B %(dmd_file)s -A %(catalog)s"
            cargs = {'dar_manager': self.cf.dar_manager_bin,
                     'dmd_file': self.dmd,
                     'catalog': catalog_path}
            crun = self.run_command(ctpl, cargs)
            dmds = self.load_dmd()
            #change the dar path so that the dmd points to the real backup
            dmd = dmds[catalog_id]

            ntpl = "%(dar_manager)s -B %(dmd_file)s -p %(id)s %(path)s"
            archivestore = os.path.join(self.cf.archive_store, self.section)
            cargs.update({'id': dmd.num, 'path': archivestore})
            nrun = self.run_command(ntpl, cargs)
        except IOError:
            self.logger.debug("Extracting catalog %s from %s.." %
                              (catalog_path, archive_path))
            _c_dir = os.path.dirname(catalog_path)
            if not os.path.exists(_c_dir):
                os.makedirs(_c_dir)
            ntpl = "%(dar)s -C %(catalog_path)s -A %(archive_path)s"
            args = {'dar': self.cf.dar_bin,
                    'catalog_path': catalog_path,
                    'archive_path': archive_path}
            run = self.run_command(ntpl, args)
            if run[0].returncode == 0:
                self.add_to_dmd(catalog_id)
            else:
                raise CatalogException(
                    'Couldn\'t extract catalog from %s.' % archive_path)

    def mk_bkp_args(self, basename):
        if self.newcatalog.type == self.Full:
            tpl = commands['full_bck']
        else:
            tpl = commands['inc_bck']
            #check for reference catalog's presence
            refcatalog = os.path.join(
                self.cf.catalog_store,
                self.Job.name,
                self.refbasename.id)
            if len(glob.glob("%s.*.dar" % refcatalog)) > 0:
                self.args.update({'refcatalog': refcatalog})
            else:
                raise RefCatalogError(
                    "Can't find the reference catalog: (%s)" % refcatalog)

        self.logger.debug(self.cf.compr)

        if self.cf.compr:
            tpl += bakup_extra['compr']
            tpl += bakup_extra['compr_min']
            tpl += bakup_extra['compr_exempt']
        if self.cf.slice:
            tpl += bakup_extra['slice']
        if self.cf.encryption:
            command_file = mk_dar_crypt_file(self.cf.encryption)
            self.logger.debug('Creating encryption command file %s' %
                              command_file)
            self.args['encryption'] = command_file
            tpl += bakup_extra['encryption']
            self.newcatalog.enc = True
        if self.cf.same_fs:
            tpl += bakup_extra['same_fs']
        if self.cf.exclude_regex:
            tpl += bakup_extra['exclude_regex']
        if self.cf.exclude_file:
            tpl += bakup_extra['exclude_file']

        #par_local MUST come after par template, as dar "-E" commands are
        #executed in the order they appear on the command line
        if self.cf.redundancy:
            tpl += bakup_extra['par']
            if self.cf.par_local:
                tpl += bakup_extra['par_local']

        #If par & par_local are True, dump the backup to local_store,
        #as a "-E" dar command will move the basename to the archive_storage
        if self.cf.redundancy and self.cf.par_local:
            mkdir(self.cf.local_store, self.section)
            self.args.update({'basename': os.path.join(
                self.cf.local_store, self.Job.name, basename)})
        else:
            self.args.update({'basename': os.path.join(
                self.cf.archive_store, self.Job.name, basename)})

        self.args.update({'catalog': os.path.join(
            self.cf.catalog_store,
            self.Job.name, basename)})
        return tpl

    def load_dmd(self):
        '''Load a dar_manager listing into a dictionary of namedtuples indexed
        by archive name.'''
        rdict = {}
        tpl = "%(dar_manager)s -B %(dmd_file)s -l -Q"
        args = {'dar_manager': self.cf.dar_manager_bin, 'dmd_file': self.dmd}
        run = self.run_command(tpl, args)
        Dmd = namedtuple('Dmd', ['num', 'path'])
        r = re.compile(
            r"\s+(?P<num>\d+)\s+(?P<path>.*)\s+(?P<id>\w+)")
        out = run[1][0].split("\n")[6:]
        for line in out:
            m = r.match("\t %s" % line)
            if m:
                rdict[m.group('id')] = Dmd(m.group('num'), m.group('path'))
        self.logger.debug(rdict)
        return rdict

    def search_dmd(self, sfile):
        '''Search the dmd for versions of a file'''
        args = {'dar_manager': self.cf.dar_manager_bin, 'dmd_file': self.dmd,
                'sfile': sfile}
        tpl = "%(dar_manager)s -B %(dmd_file)s -f %(sfile)s -Q"
        run = self.run_command(tpl, args)
        return parsedar_dates(run[1][0].split("\n")[2:])

    def recover_from_dmd(self, path, tmp_path, when=None):
        '''Perform a dar_manager recovery'''
        if isinstance(path, list):
            path = " ".join(path)

        args = {'dar_manager': self.cf.dar_manager_bin, 'dmd_file': self.dmd,
                'path': path, 'tmp_path': tmp_path}
        tpl = "%(dar_manager)s -B %(dmd_file)s "

        tpl += ' -e "-Q -w -R %(tmp_path)s '
        if self.cf.encryption:
            command_file = mk_dar_crypt_file(self.cf.encryption)
            self.logger.debug('Creating encryption command file %s' %
                              command_file)
            tpl += '-B %s ' % command_file

        if not is_admin():
            tpl += ' --comparison-field=ignore-owner '

        #Close the -e quote.
        tpl += ' " '

        if when:
            tpl += "-w %(when)s "
            args['when'] = when

        tpl += "-Q -r %(path)s "

        self.logger.debug(tpl)
        rval = self.run_command(tpl, args)
        if self.cf.encryption and os.path.exists(command_file):
            self.logger.debug('Deleting encryption command file %s' %
                              command_file)
            os.unlink(command_file)
        return rval

    def recover_all(self, rpath, stdout=sys.stdout, stderr=sys.stderr,
                    catalog=None):
        '''Perform a dar recovery'''

        tpl = "%(dar_bin)s -R %(recover_path)s -w -x %(archive_path)s "
        q = self.sess.query(Catalog)

        if not catalog:
            last = q.filter(and_(Catalog.clean,
                                 Catalog.job == self.Job,
                                 Catalog.type == self.Full
                                 )).order_by(Catalog.date.desc()).first()
            childs = getchilds(last)
        else:
            try:
                last = q.filter_by(id=catalog).one()
                childs = getancestors(last)
            except NoResultFound, e:
                raise RecoverError("% s is not a valid jobid." % catalog)

        if not is_admin():
            tpl += "-O ignore-owner "

        if self.cf.encryption:
            command_file = mk_dar_crypt_file(self.cf.encryption)
            self.logger.debug('Creating encryption command file %s' %
                              command_file)
            tpl += '-B %s ' % command_file

        args = {'dar_bin': self.cf.dar_bin, 'recover_path': rpath}

        #If catalog was given, we need to sort the list.
        all_archives = sorted([last] + childs, key=lambda x: x.date)
        self.logger.debug("Restoring from: %s" % all_archives)
        _err = False
        for arch in all_archives:
            stdout.write("Recovering %s archive id: %s..\n" %
                         (arch.type.name, arch.id))

            args['archive_path'] = os.path.join(
                self.cf.archive_store, self.Job.name, arch.id)
            run = self.run_command(tpl, args)

            if run[1][0]:
                stdout.write("Stdout was:\n %s\n" % run[1][0])

            if run[1][1]:
                stderr.write("Stderr was:\n %s\n" % run[1][1])

            if run[0].returncode > 0:
                _err = True

        if _err:
            stderr.write("WARNING, At least one operation returned a non cero"
                         " returncode\n")

        if self.cf.encryption and os.path.exists(command_file):
            self.logger.debug('Deleting encryption command file %s' %
                              command_file)
            os.unlink(command_file)


def dar_move(cmd=None, sect=None):
    '''Entry point console script for moving slices'''
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser(description='Move dardrive slices.\n')
    parser.add_argument('-j', '--job', required=True, help="Job name")
    parser.add_argument('-i', '--id', required=True, help='Dar base')
    parser.add_argument(
        '-s', '--slice', required=True, type=int, help="Slice number")
    #Check if we've been called as an entry point console-script.
    if cmd is not None:
        opts = parser.parse_args(cmd)
    else:
        opts = parser.parse_args()

    if sect is None:
        cf = Config("~/.dardrive/jobs.cfg", DARDRIVE_DEFAULTS)
        try:
            sect = getattr(cf, opts.job)
        except ConfigSectionException, e:
            sys.stderr.write('Invalid job name "%s"\n' % opts.job)
            sys.exit(1)

    r = Report(opts.job)
    try:
        cat = r.get_catalogs(catalog=opts.id).one()
    except NoResultFound, e:
        sys.stderr.write('Invalid backup id "%s"\n' % opts.id)
        sys.exit(1)

    fname = "%s.%s.%s" % (cat.id, opts.slice, find_ext(cat.type.name))
    origin = os.path.join(sect.local_store, opts.job, fname)
    dest = os.path.join(sect.archive_store, opts.job)

    start_time = time.time()

    for each in glob.glob("%s*" % origin):
        if os.path.isdir(sect.archive_store):
            shutil.move(each, dest)
            sys.stdout.write("%s moved to %s\n" % (os.path.basename(each),
                                                   dest))
        else:
            sys.stderr.write("%s's archive_store (%s) must be a directory\n" %
                             sect.archive_store)
            sys.exit(1)
    end_time = time.time()
    secs = int(end_time - start_time)
    sys.stdout.write('Slice %s moved in %s\n' %
                     (opts.slice, datetime.timedelta(seconds=secs)))


def dar_par(mode="Testing", cmd=None, output=sys.stdout):
    '''Entry point console script for creating/testing par2 files.
    Warning: dar_par assumes that the las directory in path is the jobname.
    '''
    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser()
    for arg in ['path', 'basename', 'slice', 'extension', 'context']:
        parser.add_argument(arg)
    if mode == "Creating":
        parser.add_argument('redundancy')

    #Check if we've been called as an entry point console-script.
    if cmd is not None:
        opts = parser.parse_args(cmd)
    else:
        opts = parser.parse_args()

    jobname = opts.path.strip("/").split("/")[-1]
    cf = Config("~/.dardrive/jobs.cfg", DARDRIVE_DEFAULTS)
    cs = getattr(cf, jobname)

    par_bin = cs.par_bin
    try:
        check_file(par_bin)
    except IOError, e:
        sys.stderr.write('Disabling parity data-recovery archive:\n %s\n' %
                         e.message)
        sys.exit(1)
    output.write(mode + " PAR files for %s.%s.%s ..\n" % (
        opts.basename,
        opts.slice,
        opts.extension))

    if mode == "Testing":
        pfiles = glob.glob("%s/%s.%s.%s*par2" %
                           (opts.path,
                            opts.basename,
                            opts.slice,
                            opts.extension))

        if len(pfiles) > 2:
            raise ParException("ERROR: there's, no parity information "
                               "for this job id! ")

    if mode == "Creating":
        args = shlex.split('%s c -q -q -r%s -m%s -n1 "%s/%s.%s.%s"' % (
                           cs.par_bin, opts.redundancy, cs.par_mem, opts.path,
                           opts.basename, opts.slice, opts.extension))
    else:
        args = shlex.split('%s v -q -q -m%s "%s/%s.%s.%s"' % (
                           cs.par_bin, cs.par_mem, opts.path, opts.basename,
                           opts.slice, opts.extension))
    logger.debug(" ".join(args))
    command = subprocess.Popen(args, **commands['popen_defaults'])
    start_time = time.time()
    result = command.communicate()
    end_time = time.time()
    ttook = datetime.timedelta(seconds=int(end_time - start_time))
    output.write("%s\n" % result[0])

    if command.returncode == 0:
        if mode == "Testing":
            output.write("Repair is not required, time took: %s\n" % ttook)

        else:
            output.write("Recovery files created, time took: %s\n" % ttook)
    else:
        if cmd is None:
            sys.exit(command.returncode)
        else:
            if mode == "Testing" and command.returncode == 1:
                raise ParException("Recovery needed for %s!" % opts.basename)
                sys.exit(command.returncode)
            else:
                output.write("Error, par2 exited with %s\n"
                             % command.returncode)

    if cmd is None:
        sys.exit(command.returncode)


dar_par_create = lambda: dar_par("Creating")
dar_par_test = lambda: dar_par("Testing")
