import os
from sqlalchemy import create_engine
path = os.path.dirname(__file__)

engine = create_engine('sqlite:///:memory:', echo=False)

CONFIGFILE = os.path.join(path, "test_jobs.cfg")

#this is used by the duc files
PAR_BIN = "/usr/bin/par2"
