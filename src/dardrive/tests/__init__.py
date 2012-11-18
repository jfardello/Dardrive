import sys

import os, shutil, errno
import unittest
import doctest
import config
import purge
import stats
import last_run
import xattr
import validators
import locks


TMPDIR = "/tmp/testdardrive"
ARCH="arch"
CAT="cat"
def clean(doc):
    if os.path.exists(TMPDIR):
        shutil.rmtree(TMPDIR, ignore_errors=True)

def setup(doc):
    clean(doc)
    try:
        os.makedirs(os.path.join(TMPDIR, CAT))
        os.makedirs(os.path.join(TMPDIR, ARCH))
    except OSError as exc: 
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise


def suite():
    suite = unittest.TestSuite()
    suite.addTests(doctest.DocTestSuite(config, setUp=setup))
    suite.addTests(doctest.DocTestSuite(validators))
    suite.addTests(doctest.DocTestSuite(locks))
    suite.addTests(doctest.DocTestSuite(purge))
    suite.addTests(doctest.DocTestSuite(stats))
    suite.addTests(doctest.DocTestSuite(last_run))
    suite.addTests(doctest.DocTestSuite(xattr, tearDown=clean))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
