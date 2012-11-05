from __future__ import print_function
import os
import sys
import re
import pwd
import errno
import string
import ConfigParser
from socket import getfqdn
import socket
import smtplib
import datetime
from random import choice, randint
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from collections import namedtuple

import xattr
from excepts import *


CIPHERS = ["blowfish", "bf", "aes", "twofish", "serpent", "camellia",
           "scrambling", "scram"]

STTS_TPL = '''import os, logging
from sqlalchemy import create_engine
path = os.path.dirname(__file__)

dbfile = os.path.join(path, "dardrive.db")

#see http://docs.sqlalchemy.org/en/rel_0_7/core/engines.html
engine = create_engine('sqlite:///%s' % dbfile, echo=False)

CONFIGFILE = "~/.dardrive/jobs.cfg"
LOGLEVEL = logging.ERROR

'''


def check_file(file_name, exception=None):
    '''Expand ~ and ~user strings in file_name and raises IOError if the
    expanded file doesn't exists'''
    if exception is None:
        exception = ConfigFileException
    file_name = os.path.realpath(os.path.expanduser(file_name))
    if not os.path.exists(file_name):
        raise exception('No such file: %s' % file_name)
    return file_name


def validate_file(key, value, type, exception=None):
    return check_file(value, exception)


def validate_nostring(key, value, type, exception=None):
    if not exception:
        exception = ConfigValidationException
    if value.lower() in ["1", "yes", "true", "on"]:
        raise exception(
            '"%s" allows config parser\'s "no" values or strings, true'
            ' booleans are not allowed' % key)
    elif value.lower() in ["no", "0", "off", "false"]:
        return False
    else:
        return value


def validate_noint(key, value, _type, exception=None):
    if not exception:
        exception = ConfigValidationException
    if value.lower() in ["0", "no", "off", "false"]:
        return False
    else:
        return _type(value)


def validate_nofile(key, value, type, exception=None):
    if value.lower() in ["no", "0", "off", "false"]:
        return False
    else:
        return validate_file(
            key,
            validate_nostring(key, value, type, exception),
            type,
            exception)


def validate_dar_pass(key, value, type, exception=None):
    if not exception:
        exception = ConfigValidationException
    if value.lower() in ["no", "0", "off", "false"]:
        return False
    try:
        algo, passwd = value.split(":", 1)
        if algo not in CIPHERS:
            raise exception('Cipher not allowed(%s)' % algo)
        if passwd is "":
            raise ConfigPasswdException('Password string can\'t be empty')
        return value

    except ValueError:
        raise exception(
            '"%s" should be algo:pass string as seen in DAR(1) but without'
            ' empty values' % key)


def validate_date(key, value, type, exception=None):
    if not exception:
        exception = ConfigValidationException
    try:
        t = datetime.datetime.strptime(value, '%Y-%m-%d')
        return value
    except ValueError:
        raise exception(
            '"%s" is not a valid date, please use the "yyyy-mm-dd" format' %
            key)


def validate_dar_slice(key, value, type, exception=None):
    if not exception:
            exception = ConfigValidationException
    if value.isdigit():
        return value
    try:
        int_part = int(value[:-1])
        unit_part = value[-1]
        if value[-1] not in ["k", "K", "M", "G", "T", "P", "E", "Z", "Y"]:
            raise exception('%s: invalid format see DAR(1)' % key)
        return value
    except ValueError:
        raise exception('%s: invalid format, see DAR(1)' % key)


__user_name = pwd.getpwuid(os.getuid()).pw_name


class Op(namedtuple('Op', ['value', 'type', 'validator'])):
    '''A namedtuple with defaults, used to know the default value, type and
    validator function.

    ex: {'slice': Op('2048M', str, callable)}

        The "callable" will be called with args : key, value, type,
        exception[=None] and it is meant to raise a validation exception.

    '''

    def __new__(cls, value, type, validator=lambda k, v, t, e=None: v):
        return super(Op, cls).__new__(cls, value, type, validator)

DARDRIVE_DEFAULTS = {
    'archive_store': Op('/mnt/bakcups/', str),
    'catalog_store': Op('/mnt/bakcups/catalogs', str),
    'catalog_begin': Op(str(datetime.date.today()), str, validate_date),
    'compr': Op('no', str, validate_nostring),
    'compr_exempt': Op(".*\.(gz|bz2|png|jpg|zip)", str),
    'compr_level': Op('6', int),
    'compr_min': Op('300', int),
    'dar_bin': Op('/usr/bin/dar', str, validate_file),
    'dar_manager_bin': Op('/usr/bin/dar_manager', str, validate_file),
    'recover_path': Op('/tmp', str),
    'diffdays': Op('7', int),
    'email_from': Op("%s@%s" % (__user_name, getfqdn()), str),
    'email_to': Op("%s@%s" % (__user_name, getfqdn()), str),
    'exclude_file': Op("no", str, validate_nofile),
    'exclude_regex': Op("no", str, validate_nostring),
    'encryption': Op("no", str, validate_dar_pass),
    'local_store': Op('/tmp/dardrive-%s' % __user_name, str),
    'mysql': Op('no', bool),
    'mysql_compr': Op('no', bool),
    'mysql_host': Op('localhost', str),
    'mysql_user': Op(__user_name, str),
    'mysql_pass': Op('changeme', str),
    'openssl_bin': Op('/usr/bin/openssl', str, validate_file),
    'par_bin': Op('/usr/bin/par2', str, validate_file),
    'par_local': Op('yes', bool),
    'par_mem': Op('64', int),
    'redundancy': Op('2', int, validate_noint),
    'report_success': Op('no', bool),
    'root': Op('/home/' + __user_name, str),
    'same_fs': Op('no', bool),
    'send_email': Op('no', bool),
    'slice': Op('2048M', str, validate_dar_slice),
    'smtp_server': Op("localhost:25", str),
    'smtp_user': Op(__user_name, str),
    'smtp_pass': Op("secret", str),
    'subject': Op('Backup report', str),
}


DAR_STATUSES = (
    'Operation succeded.',
    'Syntax error on command-line.',
    'Error due to a hardware problem or a lack of memory.',
    'Application bug.',
    'Dar aborted due to lack of user interaction.',
    'Error concerning the treated data (permissions,io,etc). '
    'See dar\'s manual (Exit code 5).',
    'An  error  occurred  while  executing  user command (given '
    'with -E or -F option).',
    'Libdar api error.',
    'Finite length integer over-flow occurred, "infinint" is needed '
    'to to avoid this error.',
    'Unknown error.',
    'Feature disabled at compilation time.',
    'Some saved files have changed while dar was reading them.'
)

dar_status = lambda x: DAR_STATUSES[x]


def mkdir(ddir, section=False):
    '''Try to recursively create a directory.'''
    if section:
        ddir = os.path.join(ddir, section)
    try:
        if not os.path.exists(ddir):
            os.makedirs(ddir, 0700)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise e

#TODO: consolidate all mk_*_auth stuff


def mk_ssl_auth_file(passwd):
    chars = string.ascii_letters + string.digits
    name = "".join(choice(chars) for x in range(randint(8, 12)))
    file_name = os.path.join(check_file("~/.dardrive"), "%s" % name)
    fd = os.open(file_name, os.O_WRONLY | os.O_CREAT, 0600)
    with os.fdopen(fd, 'w') as cnf:
        cnf.write("%s\n" % passwd)
        cnf.flush()
    return file_name


def mk_mysql_auth_file(**kw):
    name = kw.pop('id')
    tpl = ["[client]",
           "host     = %(mysql_host)s",
           "user     = %(mysql_user)s",
           "password = %(mysql_pass)s\n"]
    file_name = os.path.join(
        check_file("~/.dardrive"),
        "%s.cnf" % name)
    fd = os.open(file_name, os.O_WRONLY | os.O_CREAT, 0600)
    with os.fdopen(fd, 'w') as cnf:
        cnf.write("\n".join(tpl) % kw)
        cnf.flush()
    return file_name


def mk_dar_crypt_file(encryption):
    chars = string.ascii_letters + string.digits
    name = "".join(choice(chars) for x in range(randint(8, 12)))
    try:
        algo, passwd = encryption.split(":")[:2]
    except ValueError:
        ConfigValidationException(
            'Bad encryption string, should be '
            '"<algorithm>:<password>" see the dar manual page.')
    if algo not in CIPHERS:
        raise ConfigValidationException('Unsupported cypher: %s' % algo)

    tpl = "-K %s:%s\n"
    file_name = os.path.join(
        check_file("~/.dardrive"),
        "%s" % name)
    fd = os.open(file_name, os.O_WRONLY | os.O_CREAT, 0600)
    with os.fdopen(fd, 'w') as cnf:
        cnf.write(tpl % (algo, passwd))
        cnf.flush()
    return file_name


def userconfig():
    '''Creates the user config dir if it doesn't exists'''
    path = os.path.expanduser('~/.dardrive')
    config_file = os.path.join(path, 'jobs.cfg')
    settings_file = os.path.join(path, 'setts.py')
    mkdir(path)
    mkdir(os.path.expanduser('~/.dardrive/dmd'))
    if not os.path.exists(config_file):
        cf = ConfigParser.RawConfigParser()
        cf.add_section('global')
        for k in DARDRIVE_DEFAULTS.keys():
            cf.set('global', k, DARDRIVE_DEFAULTS[k][0])

        fd1 = os.open(config_file, os.O_WRONLY | os.O_CREAT, 0600)
        with os.fdopen(fd1, 'w') as configfile:
                cf.write(configfile)
                sys.stdout.write("Config file written.\n")

    if not os.path.exists(settings_file):
        fd2 = os.open(settings_file, os.O_WRONLY | os.O_CREAT, 0600)
        with os.fdopen(fd2, 'w') as stts:
            stts.write(STTS_TPL)
            sys.stdout.write("Settings file written.\n")


def send_email(cf, text, error=False):
    '''Send emails, cf must be a ConfigSection'''
    msg = MIMEMultipart()
    msg['From'] = cf.email_from
    msg['To'] = COMMASPACE.join(cf.email_to.split(','))
    msg['Date'] = formatdate(localtime=True)
    if error:
        msg['Subject'] = cf.subject + " (error)"
    else:
        msg['Subject'] = cf.subject
    msg.attach(MIMEText(text, 'plain', 'utf8'))
    smtp = smtplib.SMTP(cf.smtp_server)
    port = 25
    try:
        port = int(cf.smtp_server.split(":")[1])
    except (IndexError, ValueError):
        pass
    if port == 587:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(cf.smtp_user, cf.smtp_pass)

    smtp.sendmail(cf.email_from, cf.email_to.split(","), msg.as_string())
    smtp.close()


def reindent(s, numSpaces):
    s = string.split(s, '\n')
    s = [(numSpaces * ' ') + string.lstrip(line) for line in s]
    s = string.join(s, '\n')
    return s


def ordinal(num):
    if num == 0:
        return "0"
    if 4 <= num <= 20 or 24 <= num <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][num % 10 - 1]
    return "%s%s" % (num, suffix)


def mk_dar_date(dt):
    '''Return a date string suitable for dar_manared -w switch, which is
    datetime dt + 1 second (as dar_manager restores the latest file before
    this date).

        mk_dar_date(datetime.datetime) -> string 'YYYY/MM/DD-HH:mm:ss'

    '''
    dt = dt + datetime.timedelta(seconds=1)
    return dt.strftime('%Y/%m/%d-%H:%M:%S')


def parsedar_dates(lines):
    '''Returns a list of dates from the split output of dar_manager -f
    which represent all the different timestaps stored for a file.'''
    date_exp = re.compile(
        r'''
        ^.*                 #anything outside the group
        ([A-Z][a-z]{2}      #abbr week day as in %a
        \s+                 #space
        [A-Z][a-z]{2}       #abbr month name as in %b
        \s+                 #space
        \d{1,2}             #month day as in %d
        \s+                 #space
        \d{2}:\d{2}:\d{2}   #hour 00:00:00
        \s+                 #space
        \d{4})              #year as in %Y (YYYY)
        .*$                 #anything outside the group
        ''', re.VERBOSE)
    dts = []
    for line in lines:
        m = date_exp.match(line)
        if m:
            dts.append(datetime.datetime.strptime(
                m.group(1), '%a %b %d %H:%M:%S %Y'))
    return dts


def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def save_xattr(cat, cf):
    '''Save basic db data as extended attributes on the first slice of a
    backup file.'''
    fl = os.path.join(cf.archive_store, cat.job.name, cat.id)
    if cat.type.name == "MysqlDump":
        fl += ".1.dmp"
    elif cat.type.name == "gzMysqlDump":
        fl += ".1.dmp.gz"
    else:
        fl += ".1.dar"

    x = xattr.xattr(fl)
    x["user.dardrive.type"] = str(cat.type.name)
    x["user.dardrive.job"] = str(cat.job.name)
    if cat.comment:
        x["user.dardrive.comment"] = str(cat.comment)
    else:
        x["user.dardrive.comment"] = ""
    x["user.dardrive.date"] = str(cat.date)
    if cat.parent:
        x["user.dardrive.parent"] = str(cat.parent.id)
    else:
        x["user.dardrive.parent"] = ""
    x["user.dardrive.enc"] = str(cat.enc)
    x["user.dardrive.clean"] = str(cat.clean)
    x["user.dardrive.hierarchy"] = str(cat.hierarchy)
    x["user.dardrive.status"] = str(cat.status)
    x["user.dardrive.ttook"] = str(cat.ttook)
    x["user.dardrive.root"] = str(cf.root)


#http://code.activestate.com/recipes/577202-render-tables-for-text-interface/
class ALIGN:
    LEFT, RIGHT = '-', ''


class Col(list):
    def __init__(self, name, data, align=ALIGN.RIGHT):
        list.__init__(self, data)
        self.name = name
        width = max(len(str(x)) for x in data + [name])
        self.format = ' %%%s%ds ' % (align, width)


class Table:
    def __init__(self, *columns):
        self.columns = columns
        self.length = max(len(x) for x in columns)

    def get_row(self, i=None):
        for x in self.columns:
            if i is None:
                yield x.format % x.name
            else:
                yield x.format % x[i]

    def get_rows(self):
        yield ' '.join(self.get_row(None))
        for i in range(0, self.length):
            yield ' '.join(self.get_row(i))

    def __str__(self):
        return '\n'.join(self.get_rows())

