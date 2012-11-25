.. dardrive documentation master file, created by
   sphinx-quickstart on Mon Aug 20 11:56:44 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


.. meta::
   :description: dardrive command line backup tool
   :keywords: backup, dar, cloud, python, email reporting, catalog isolation
   :charset: UTF-8


.. |br| raw:: html
    
    <br/>


.. cssclass:: pull-right alert

    **Warning!** needs beta testing

..

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


|br|

For the impatient
-----------------

|br|

.. code-block:: console

    user@box:~/> sudo pip install \
     https://github.com/downloads/jfardello/Dardrive/dardrive-0.2.10b2.tar.gz
    [..]
    user@box:~/> dardrive init
    Config file written.
    Settings file written.

    user@box:~/> dardrive addjob docs -R /home/user/Documents/stuff \
        -A /mnt/dardrive/archive -C /mnt/dardrive/catalogs
    Job added
    user@box:~/> dardrive modjob -j docs -O 'compr=lzo'
    Job modified

    user@box:~/> dardrive backup -j docs
    Running backup job: docs..
    Dar status:             Operation successful.
    Time took:              0:01:34
    Job name:               docs 
    Catlog id:              563d78a42184429a829cbde74d4f22cb
    Status Code:            0 

    user@box:~/>
.. 
.. toctree::
    :hidden:
    :maxdepth: 1

    install.rst
    usage.rst
    dar_commands.rst
    concepts.rst
    mysql.rst
    configopts.rst
    dar_restore.rst
