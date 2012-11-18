import os
import shlex
import logging
from argparse import ArgumentParser, ArgumentError
from cmd import Cmd
from excepts import *


def mkarg(*args, **kwargs):
    return (args, kwargs)


class options(object):
    '''An argparse based decorator that deals with argument handling for
    cmd.Cmd methods, inspired by cmd2'''
    def __init__(self, args):
        self.logger = logging.getLogger(__name__)
        self._wrapped = None
        self.fname = None
        if not isinstance(args, list):
            args = [args]
        self.parser = ArgumentParser()
        for argtuple in args:
            self.parser.add_argument(*argtuple[0], **argtuple[1])

    def _deco(self, instance, args, **kwargs):
        parser_args = shlex.split(args)
        try:
            opts = self.parser.parse_args(parser_args)
            return self._wrapped(instance, args, opts=opts)
        #ArgumentParser likes to exit when arguments don't match..
        except (ArgumentError, SystemExit), e:
            instance.stdout.write("Unrecognized arguments\n")
        #catch bad jobname definitions
        except (ConfigSectionException, BackupDBException, ParException), e:
            instance.stdout.write("%s\n" % e.message)
        #catch locking and xattr exceptions.
        except (LockException, XattrException), e:
            instance.report("%s" % e.message, opts.job, error=True)

    def __call__(self, wrapped):
        self._wrapped = wrapped
        self.fname = wrapped.__name__

        def deco(instance, *args, **kwargs):
            return  self._deco(instance, *args, **kwargs)
        deco.__name__ = self.fname

        self.parser.prog = self.fname.replace("do_", "")
        deco.__doc__ = '%s\n%s' % (wrapped.__doc__, self.parser.format_help())
        return deco


class CmdApp(Cmd):
    '''A version of cmd.Cmd that doesn't show undocumented comands.'''

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        Cmd.__init__(self, *args, **kwargs)

    def do_EOF(self, line):
        self.stdout.write('\nSee ya!\n')
        return True

    def emptyline(self):
        pass

    def do_help(self, arg):
        if arg:
            Cmd.do_help(self, arg)
        else:
            names = self.get_names()
            cmds_doc = []
            help = {}
            for name in names:
                if name[:5] == 'help_':
                    help[name[5:]] = 1
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ''
            for name in names:
                if name[:3] == 'do_':
                    if name == prevname:
                        continue
                    prevname = name
                    cmd = name[3:]
                    if cmd in help:
                        cmds_doc.append(cmd)
                        del help[cmd]
                    elif getattr(self, name).__doc__:
                        cmds_doc.append(cmd)
            self.stdout.write("%s\n" % str(self.doc_leader))
            self.print_topics(self.doc_header, cmds_doc, 15, 80)
            self.print_topics(self.misc_header, help.keys(), 15, 80)
