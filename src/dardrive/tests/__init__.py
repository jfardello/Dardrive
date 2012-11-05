import sys

import os, shutil
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
def clean(doc):
    if os.path.exists(TMPDIR):
        shutil.rmtree(TMPDIR, ignore_errors=True)


def suite():
    suite = unittest.TestSuite()
    suite.addTests(doctest.DocTestSuite(config))
    suite.addTests(doctest.DocTestSuite(validators))
    suite.addTests(doctest.DocTestSuite(locks))
    suite.addTests(doctest.DocTestSuite(purge))
    suite.addTests(doctest.DocTestSuite(stats))
    suite.addTests(doctest.DocTestSuite(last_run))
    suite.addTests(doctest.DocTestSuite(xattr, setUp=clean, tearDown=clean))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
