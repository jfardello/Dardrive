Dardrive
--------

**Warning!** needs beta testing!


Dardrive is a **command line backup tool** which keeps track of backup jobs and
automates backup rotation.

It uses the `Disc ARchive <http://dar.linux.free.fr/>`_ program to store
backups and has many features such as differential backup via catalogued data,
par2 integration, per job configuration, backup rotation, email reporting, and
mysql integration among other things.

The idea behind dardrive is to store catalogs in fast media while storing the
backup content in large and slow cloud storage (it was written with `s3ql`_ in
mind). Creating differential backups against the cataloged data saves network
traffic and IOPs.

Dardrive uses a full+incremental backup scheme which saves the last full backup
from previous months as "historic" backups, you'll end up with a (time)
configurable amount of incremental archives between full backups, plus
"monthly" and "yearly" historic backups.

.. _`s3ql`: http://code.google.com/p/s3ql/

