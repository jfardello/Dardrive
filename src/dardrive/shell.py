import os
import sys
import imp
import shlex
import glob
import re
import logging
import errno
from datetime import datetime as dt
from datetime import timedelta
import socket
import subprocess
from collections import namedtuple

from dar import Scheme, dar_par
from db import Report, Importer, find_ext, Catalog, Lock
from utils import userconfig, DARDRIVE_DEFAULTS, dar_status
from utils import send_email, reindent, mk_dar_date
from utils import mk_ssl_auth_file
from config import Config
from cmdp import options, CmdApp, mkarg
from excepts import *

from sqlalchemy.orm.exc import NoResultFound

from getpass import getpass
from utils import Col, ALIGN, Table


setts_file = os.path.expanduser('~/.dardrive/setts.py')
if os.path.exists(setts_file):
    setts = imp.load_source('setts', setts_file)
else:
    Setts = namedtuple('Setts', ['CONFIGFILE', 'LOGLEVEL'])
    setts = Setts(CONFIGFILE=setts_file, LOGLEVEL=logging.ERROR)

logging.basicConfig(level=setts.LOGLEVEL)


class DardriveApp(CmdApp):
    prompt = "dardrive> "
    doc_header = "Available commands:"
    ruler = "~"
    intro = "Welcome to dardrive console.\n"

    def __init__(self, *a, **kw):
        CmdApp.__init__(self, *a, **kw)
        self.logger.debug('Init')
        try:
            self.cf = Config(os.path.expanduser(
                setts.CONFIGFILE), DARDRIVE_DEFAULTS)
        except InitException, e:
            self.stdout.write('%s\n' % e.message)
            self.stdout.write('You must init the user config first.\n')
            self.stdout.write('dardrive init \n')

            sys.exit(2)

    def report(self, text, job, verbose=False, catalog=False, error=False):
        '''Report to console and send email notifications if jobs are
        configured to do so'''
        assert job in self.cf.sections()
        cf = getattr(self.cf, job)

        text += "Job name:\t\t%s \n" % job
        mail_text = text
        if catalog:
            text += "Catalog id:\t\t%s\nStatus Code:\t\t%s \n" % (catalog.id,
                    catalog.status)
            mail_text = text + "Transcript:\n\n%s\n" % reindent(catalog.log, 4)
            if verbose:
                text += "Transcript:\n\n%s\n" % reindent(catalog.log, 4)

        try:
            if error:
                if cf.send_email:
                    send_email(cf, mail_text, error=True)
            else:
                if cf.send_email and cf.report_success:
                    send_email(cf, mail_text)
        except socket.error, e:
            self.stdout.write(
                "ERROR, could not contact to the smtp server: \n")
            self.stdout.write(reindent(e.message, 4) + "\n")
        self.stdout.write(text + "\n")

    @options([mkarg('-j', '--job', help="Backup job", required=True)])
    def do_dbdump(self, arg, opts=None):
        '''Run an mysql backup job'''
        if opts:
            try:
                s = Scheme(self.cf, opts.job)
                self.stdout.write('Running SQL backup job..\n')
                cat = s.db_backup()
                if cat.clean:
                    self.report('Backup completed successfully\n',
                                opts.job, catalog=cat)
                else:
                    self.report('Error running backup\n',
                                opts.job, catalog=cat, error=True)

            except (BackupDBException, ConfigException), e:
                    self.report(e.message, opts.job, error=True)
            except IOError, e:
                    self.report(e.message, opts.job, error=True)

    @options([
        mkarg('-j', '--job', help="Backup job", required=True),
        mkarg('-v', '--verbose', help="Verbose output", action="store_true",
              default=False),
        mkarg('-R', '--root', help="Override bkp root path.", default=None),
        mkarg('-f', '--full', help="Force a full backup", default=False,
              action="store_true")])
    def do_backup(self, arg, opts=None):
        '''Perform a backup task'''
        if opts:
            try:
                s = Scheme(self.cf, opts.job, opts.root)
                self.stdout.write('Running backup job: %s..\n' % opts.job)
                s.run(opts.full)
                ttook = timedelta(seconds=s.newcatalog.ttook)
                stat = dar_status(s.newcatalog.status)
                self.report('Dar status:\t\t%s\nTime took:\t\t%s\n' %
                            (stat, ttook), opts.job, verbose=opts.verbose,
                            catalog=s.newcatalog)

            except RefCatalogError, e:
                self.report(
                    'The reference catalog is missing, please '
                    'provide one or force a full backup.\n',
                    opts.job, error=True)
            except ConfigException, e:
                self.report(
                    '\nThere seems to be a configuration error:\n'
                    '    %s\n' % e.message, opts.job, error=True)
            except OSError, e:
                if e.errno == errno.EACCES:
                    self.report(
                        '\nThere seems to be a permission error:\n'
                        '   %s\n' % e.message, opts.job, error=True)

        else:
            self.stdout.write('Arguments needed  (use -h for help)\n')

    @options([
        mkarg('action', choices=("jobs", "logs", "archives", "files"),
              default="archives"),
        mkarg('-l', '--long', action='store_true', help="Show job details."),
        mkarg('-j', '--job', help="Filter by job", default=None),
        mkarg('-i', '--id', help="Filter by id", default=None),
        mkarg('-b', '--base', help="When showing files, show only dar "
              " archive base (excluding isolated catalogs)", default=False,
              action="store_true"),
        mkarg('-n', '--num', help="Limit number of log|archives entries",
              default=None),
        mkarg('-t', '--type', help="filter by type", action='append',
              default=None)])
    def do_show(self, arg, opts=None):
        '''Shows various listings'''
        # show jobs
        if opts.action == "jobs" and opts.long:
            if opts.job and opts.job not in self.cf.sections():
                raise ConfigSectionException(
                    "Unexistent job: %s" % opts.job)
            for sect in self.cf.sections():
                if opts.job and sect != opts.job:
                    continue
                else:
                    self.stdout.write('%s:\n' % sect)
                    each_sect = getattr(self.cf, sect)
                    for eopt in each_sect.options():
                        self.stdout.write('\t%s: %s\n' % (
                            eopt, getattr(each_sect, eopt)))
        elif opts.action == "jobs":
            self.stdout.write('\n'.join(self.cf.sections()) + "\n")

        # show logs
        elif opts.action == "logs":
            if opts.job and opts.id:
                    self.stdout.write(
                        " -c and -j are mutually exclusive options.\n")
            else:
                r = Report(opts.job)
                for cat in r.get_catalogs(catalog=opts.id, types=opts.type,
                                          entries=opts.num):
                    log_str = "%s\n%s\n%s\n\n%s\n" % (
                        "=" * 32, cat.id, "=" * 32, cat.log)
                    self.stdout.write(log_str)
        # show files
        elif opts.action == "files":
            if opts.id is None and opts.job is None:
                self.stdout.write("show files requires either "
                                  "-j or -i options.\n")
            else:
                try:
                    r = Report(opts.job)
                except NoResultFound:
                    self.stdout.write("Unexistent job: %s\n" % opts.job)
                    return
                ct = r.get_catalogs(catalog=opts.id, types=opts.type)

                for each in ct:
                    if not opts.base:
                        sect = getattr(self.cf, each.job.name)
                        arc = glob.glob("%s/%s/%s.*" %
                                        (sect.archive_store,
                                         each.job.name, each.id))
                        cat = glob.glob("%s/%s/%s.*" %
                                        (sect.catalog_store,
                                         each.job.name, each.id))

                        for fl in arc + cat:
                            self.stdout.write("%s\n" % fl)
                    else:
                        sect = getattr(self.cf, each.job.name)
                        self.stdout.write("%s/%s/%s\n" %
                                          (sect.archive_store,
                                           each.job.name, each.id))

        # Show archives
        elif opts.action == "archives":
            if opts.id:
                r = Report(opts.job)
                ar = r.s.query(Catalog).get(opts.id)
                if ar is not None:
                    self.stdout.write("%s\n" % self._archive_info(ar))
                else:
                    self.stdout.write("Unexistent job id.\n")

            else:
                r = Report(opts.job)
                ids = []
                names = []
                types = []
                dates = []
                statuses = []
                for cat in r.get_catalogs(types=opts.type, entries=opts.num):
                    ids.append(cat.id)
                    names.append(cat.job.name)
                    types.append(cat.type.name)
                    dates.append(cat.date.strftime("%d/%m/%y %H:%M:%S"))
                    statuses.append(str(cat.status))

                self.stdout.write("%s\n" % Table(
                    Col("Archive Id", ids, "-"),
                    Col("Job name", names),
                    Col("Job type", types),
                    Col("Created", dates),
                    Col("Dar Status", statuses)))

    def _archive_info(self, i):
        status = "Unknown"
        if i.status is not None:
            status = dar_status(int(i.status))
        else:
            r = Report(i.job.name)
            locks = r.s.query(Lock).filter(Lock.cat_id == i.id).all()
            for l in locks:
                if l.check_pid():
                    status = "Running"
                break

        return Table(
            Col("", ["Job ID", "Job name", "Job type", "Encryption",
                     "Created", "Comment", "Clean", "Status", "Parent",
                     "Hierarchy", "Time Took"]),
            Col("", [
                i.id,
                i.job.name,
                i.type.name,
                i.enc,
                i.date.strftime("%c"),
                i.comment,
                i.clean,
                status,
                i.parent,
                i.hierarchy,
                #when running ttookk will be none, we must figutre out
                #how much has been taking.
                timedelta(seconds=(dt.now() - i.date).total_seconds())
                ], "-"))

    @options([
        mkarg('action', choices=("create", "test"), default="test"),
        mkarg('-i', '--id', required=True, help="Specifies the jobid.")])
    def do_parity(self, arg, opts):
        '''Generate "par2" error correction files.'''
        r = Report(None)
        ct = r.get_catalogs(catalog=opts.id).one()
        cf = getattr(self.cf, ct.job.name)

        if not cf.redundancy and opts.action == "create":
            raise ConfigSectionException(
                'Please enable redundacy for this job '
                'in order to build recovery information.')

        base = "%s/%s/%s.*" % (cf.archive_store,
                               ct.job.name, opts.id)
        self.logger.debug(base)
        reobj = re.compile(r'''
                ^.*\.            #anything, ending in dot
                (?P<slice>\d*)   #any number
                \.dar$           #ends in .dar
                ''', re.VERBOSE)
        for files in glob.glob(base):
            self.logger.debug(files)
            m = reobj.match(files)
            if m:
                self.logger.debug("Slice matched for %s" % m.group('slice'))
                args = [str("%s/%s" % (cf.archive_store, ct.job.name)),
                        opts.id, str(m.group('slice')), 'dar', '']
                self.logger.debug(args)
                if opts.action == "create":
                    mode = "Creating"
                    args.append(str(cf.redundancy))
                else:
                    mode = "Testing"
                try:
                    dar_par(mode=mode, cmd=args)
                except SystemExit, e:
                    status = "Ok" if e.code == 0 else "Archive needs repair!"
                    self.stdout.write("Par exited with code %s, %s\n" %
                                      (e.code, status))

    @options([
        mkarg('-f', '--file', required=True, help="File to search for"),
        mkarg('-j', '--job', required=True, help="Specifies the job")])
    def do_versions(self, arg, opts=None):
        '''Show available copies of a given file'''
        s = Scheme(self.cf, opts.job)
        for ver in s.search_dmd(opts.file):
            self.stdout.write(mk_dar_date(ver) + "\n")

    @options([mkarg('-j', '--job', required=True, help="Specifies the job")])
    def do_import(self, arg, opts=None):
        '''Import an untracked job store to db.'''
        if opts.job not in self.cf.sections():
            self.stdout.write("Unexistent job.\n")
        else:
            cs = getattr(self.cf, opts.job)
            s = Scheme(self.cf, opts.job)
            lock = s.lock('import')
            i = Importer(self.cf, opts.job, session=s.sess)
            i.load()
            self.stdout.write("Job store imported.\n")
            self.stdout.write("Rebuilding the dmd database...\n")
            dmdfile = os.path.expanduser("~/.dardrive/dmd/%s.dmd" % opts.job)
            if os.path.exists(dmdfile):
                os.unlink(dmdfile)
            s = Scheme(self.cf, opts.job)  # re-creates de dmd
            r = Report(opts.job, session=s.sess)
            for cat in r.get_catalogs(order="asc"):
                if cat.date >= dt.strptime(cs.catalog_begin, "%Y-%m-%d"):
                    s.add_to_dmd(cat.id)
            s.sess.delete(lock)
            s.sess.commit()

    @options([
        mkarg('-j', '--job', required=True, help="Specifies the job name.")])
    def do_rebuild_dmd(self, arg, opts=None):
        '''Re-creates the dmd for a given job.'''
        cf = getattr(self.cf, opts.job)
        s = Scheme(self.cf, opts.job)
        lock = s.lock("rebuild_dmd")
        self.logger.debug("Removing dmd for %s" % opts.job)
        dmdfile = os.path.expanduser("~/.dardrive/dmd/%s.dmd" % opts.job)
        if os.path.exists(dmdfile):
            os.unlink(dmdfile)
        s = Scheme(self.cf, opts.job)
        r = Report(opts.job, session=s.sess)
        for cat in r.get_catalogs(before=cf.catalog_begin, order="asc"):
            s.add_to_dmd(cat.id)
        s.sess.delete(lock)
        s.sess.commit()

    @options([
        mkarg('-f', '--file', required=True, help="File to search for"),
        mkarg('-j', '--job', required=True, help="Specifies the job"),
        mkarg('-r', '--rpath', default=None, help="Recover path"),
        mkarg('-w', '--when', default=None,
              help="Before date (in dar_managet format)")])
    def do_recover(self, arg, opts=None):
        '''Recover files through dar_manager'''
        cf = getattr(self.cf, opts.job)
        rpath = opts.rpath if opts.rpath else cf.recover_path
        s = Scheme(self.cf, opts.job)
        r = Report(opts.job, session=s.sess)

        self.logger.debug("Checking dmd sync..")

        bkp_count = r.get_catalogs(
            after=cf.catalog_begin,
            types=("Full", "Incremental")).count()
        self.logger.debug('Checking backup count on db.. %s' % bkp_count)

        dmd_count = len(s.load_dmd())
        self.logger.debug('Checking backup count on dmd.. %s' % dmd_count)

        if bkp_count != dmd_count:
            self.stdout.write("Outdated DMD please rebuild it or recover "
                              "manually.\n")
        else:
            run = s.recover_from_dmd(opts.file, rpath, when=opts.when)
            self.stdout.write("\n %s \n" % dar_status(run[0].returncode))

    @options([
        mkarg('-i', '--id', default=None, help="Limit operation to specified"
              " backup id."),
        mkarg('-j', '--job', default=None, help='Limit operation to jobname'),
        mkarg('filename', help="output filename (\"-\" for stdout)")])
    def do_dbrecover(self, arg, opts=None):
        '''Load a db backups to file or stdout, decrypting and uncompressing
        as needed.'''
        if not opts.id and not opts.job:
            sys.stderr.write("Please specify either -j or -i options.\n")
        else:
            if opts.id:
                r = Report(None)
                dmp = r.get_catalogs(catalog=opts.id)[0]
            else:
                r = Report(opts.job)
                dmp = r.get_catalogs(entries=1, types=('MysqlDump',
                                                       'gzMysqlDump'))[0]

            cs = getattr(self.cf, dmp.job.name)

            if dmp.enc and not cs.encryption:
                raise RecoverException(
                    'Archive %s is encrypted, you must '
                    'provide proper credentials in order to recover, or '
                    'recover manually.' % dmp.id)

            dmp_file = os.path.join(
                cs.archive_store,
                dmp.job.name.encode(),
                "%s.1.%s" % (
                    dmp.id.encode(),
                    find_ext(dmp.type.name)
                )
            )
            #unencrypted types
            if not cs.encryption:
                if dmp.type.name == "gzMysqlDump":
                    comm = 'zcat %s' % dmp_file
                elif dmp.type.name == "MysqlDump":
                    comm = 'cat %s' % dmp_file
            #encrypted types
            elif cs.encryption:
                pfile = mk_ssl_auth_file(cs.encryption.split(":")[1])
                if dmp.type.name == "gzMysqlDump":
                    comm = 'openssl enc -in %s -d -aes-256-cbc -pass '\
                        'file:%s | gunzip' % (dmp_file, pfile)
                elif dmp.type.name == "MysqlDump":
                    comm = 'openssl enc -in %s -d -aes-256-cbc -pass '\
                        'file:%s' % (dmp_file, pfile)

            if opts.filename == "-":
                retcode = subprocess.call(comm, shell=True)
            else:
                if os.path.exists(opts.filename):
                    raise BackupDBException('Cowardly refusing to overwrite'
                                            ' %s.' % opts.filename)
                fd = os.open(opts.filename, os.O_WRONLY | os.O_CREAT, 0600)
                with os.fdopen(fd, 'w') as out:
                    retcode = subprocess.call(comm, stdout=out, shell=True)

            if cs.encryption:
                os.unlink(pfile)
            if retcode != 0:
                sys.stderr.write("Recovery failed with status %s.\n" % retcode)

    @options([mkarg('-j', '--job', help="Show stats for job", default=False)])
    def do_stats(self, arg, opts=None):
        '''Show job statistics'''
        def stats(sect):
            if sect in self.cf.sections():
                r = Report(sect)
                self.stdout.write('%s: \n' % sect)
                for each in r.types():
                    last = r.last_run(backup_type=each)
                    avg = r.avg(backup_type=each)
                    self.stdout.write('\t %s backup: \n' % each)
                    self.stdout.write('\t\t last run time:\t%s\n' % last)
                    self.stdout.write('\t\t average time:\t%s\n' % avg)

            else:
                self.stdout.write("Can't find section %s!\n" % sect)
        if opts.job:
            stats(opts.job)
        else:
            for sect in self.cf.sections():
                try:
                    stats(sect)
                except NoResultFound:
                    self.stdout.write('There\'s no info on %s in the '
                                      'database.\n' % sect)

    def do_init(self, arg, opts=None):
        '''Creates the user config directory'''
        #actually we only need the docstring, as it is handled in shell.main()
        #and interactive mode will report an error if the user config is not
        #found
        pass

    @options([
        mkarg("jobname", help="Job name"),
        mkarg('-R', '--root', help="Job root path", required=True),
        mkarg('-A', '--archive-store', help="archive store", required=True),
        mkarg('-C', '--catalog-store', help="catalog store", default=None), ])
    def do_addjob(self, arg, opts):
        '''Adds a job definition.'''
        self.cf.add_section(opts.jobname)
        sect = getattr(self.cf, opts.jobname)
        sect.set('archive_store', opts.archive_store)
        sect.set('root', opts.root)
        if opts.catalog_store:
            sect.set('catalog_store', opts.catalog_store)
        else:
            sect.set('catalog_store', opts.archive_store)
        self.cf.sync()
        self.stdout.write("Job added\n")

    @options([
        mkarg('-j', '--job', help="Job being modified", required=True),
        mkarg('-O', '--option', help="config string", action="append",
              required=True)])
    def do_modjob(self, arg, opts):
        '''Modifies any job section option.'''
        if opts.job in self.cf.sections():
            try:
                sect = getattr(self.cf, opts.job)
                for each in opts.option:
                    self.logger.debug(each)
                    opt, val = each.strip().split("=")[:2]
                    if opt in DARDRIVE_DEFAULTS.keys():
                        try:
                            sect.set(opt, val)
                            #getattr will raise if does not validate.
                            dummy = getattr(sect, opt)
                        except ConfigPasswdException, e:
                            if sys.stdout.isatty():
                                sect.set(opt, val + getpass())
                            else:
                                raise ConfigPasswdException(
                                    'Asking for a '
                                    'password on pipe.. aborting.')
                            dummy = getattr(sect, opt)

                    else:
                        raise ConfigValidationException(
                            "%s is not a valid option." % opt)
                self.cf.sync()
                self.stdout.write("Job modified\n")

            except ConfigException, e:
                sys.stderr.write(e.message + "\n")
                sys.exit(1)
        else:
            sys.stderr.write('Unexistent job\n')
            sys.exit(1)


    def do_ls(self, arg, opts=None):
        return self.do_help(arg)

    def do_quit(self, arg, opts=None):
        '''Quits the dardrive interpreter if in interactive mode.'''
        return self.do_EOF(arg)

    def complete_backup(self, text, line, begidx, endidx):
        words = shlex.split(line)
        if words[-1] == "-j" or words[-2] == "-j":
            if words[-2] == "-j":
                sections = filter(lambda x: x.startswith(
                    words[-1]), self.cf.sections())
            else:
                sections = self.cf.sections()
            j = lambda x: "j " + x
            return map(j, sections) if not line.endswith(" ") else sections


def main():
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1].strip() == "init":
            userconfig()
        else:
            DardriveApp().onecmd(' '.join(sys.argv[1:]))
    else:
        DardriveApp().cmdloop()

if __name__ == '__main__':
    main()
