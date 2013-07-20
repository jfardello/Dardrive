import os
import sys
import shlex
import logging
from argparse import ArgumentParser, ArgumentError
from cmd import Cmd
from excepts import *


class ParserDepError(Exception):
    pass


class NestedParser(ArgumentParser):
    '''Adds a depends_on keyword to the parser that tracks argument dependency.
    Inspired by http://stackoverflow.com/questions/13788333 '''
    deps = {}

    def add_argument(self, *args, **kwargs):
        depends_on = kwargs.pop('depends_on', None)
        if depends_on:
            self.deps[args[1].strip("-")] = depends_on
        return super(NestedParser, self).add_argument(*args, **kwargs)

    def parse_args(self, *args, **kwargs):
        args = super(NestedParser, self).parse_args(*args, **kwargs)
        for arg, depends_on in self.deps.iteritems():
            try:
                if getattr(args, arg) and not getattr(args, depends_on):
                    raise ParserDepError(
                        '--%s depends on the --%s switch' % (arg, depends_on)
                    )
            except AttributeError:
                pass
        return args


def mkarg(*args, **kwargs):
    return (args, kwargs)


class options(object):
    '''An argparse based decorator that deals with argument handling for
    cmd.Cmd methods, inspired by cmd2'''
    def __init__(self, args):
        self.logger = logging.getLogger(__name__)
        self._wrapped = None
        self.fname = None
        self.groups = {}
        self.opt_groups = {}
        if not isinstance(args, list):
            args = [args]
        self.parser = NestedParser()
        for argtuple in args:
            #we add an optional "group" keyword to know if we must
            #group arguments via argparse.add_mutually_exclusive_group()
            if "group" in argtuple[1]:
                group = argtuple[1].pop('group')
                if group not in self.groups:
                    self.groups[group] = self.parser\
                        .add_mutually_exclusive_group(required=True)

                self.groups[group].add_argument(*argtuple[0], **argtuple[1])
            elif "opt_group" in argtuple[1]:
                group = argtuple[1].pop('opt_group')
                if group not in self.opt_groups:
                    self.opt_groups[group] = self.parser\
                        .add_mutually_exclusive_group()
                self.opt_groups[group].add_argument(
                    *argtuple[0], **argtuple[1])
            else:
                self.parser.add_argument(*argtuple[0], **argtuple[1])

    def _deco(self, instance, args, **kwargs):
        parser_args = shlex.split(args)
        try:
            opts = self.parser.parse_args(parser_args)
            return self._wrapped(instance, args, opts=opts)
        #ArgumentParser likes to exit when arguments don't match..
        except ParserDepError, e:
            instance.stdout.write(" Error:  %s\n" % e.message)
            sys.exit(2)
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
        for key in self.parser.deps.keys():
            deco.__doc__ += "\n    --%s depends on the --%s switch\n" %\
                (key, self.parser.deps[key])
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
