
MySQL integration
=================

Dardrive dumps all databases the MySQL user is able to access via mysql_dump. 

Mysql dumps are enabled by the boolean option ``mysql``. Dumps are 
mysqldump output files in SQL format stored it in the archive_store, optionally
compressed and encrypted. The ``mysql_compr``, ``mysql_host``, ``encryption``
``mysql_user`` and ``mysql_password`` options may alter the resulting archive.. 

When dumping a database, dardrive will pass the authentication credentials via
a temporary file with the "--defaults-extra-file" mysqldump switch.

If mysql_compr is defined dardrive will pipe the dump through gzip and will
change the job type from dbdump to dbdump.gz.

If encryption is set, the the password is extracted from the from the substring
represening the password (the part that comes after the semicolon ":"),
whatever the algorithm is set to, mysql encription is set to OpenSSL's
aes-256-cbc cipher, dardrive will create a temporary file fo storing that
password and pipe the dump command through the openssl command.

Database dumps behave much more as a filesystem jobs, they are affected by the
``par``, ``par_redundancy`` options producing error correction archives, can be
listed, its logs and time statistics are saved to the dardrive database, and
they are rotated exactly as full filesystem jobs. 


Dumping a database
------------------

Add the mysql options that the job needs::

    ~/>dardrive modjob -j myjob -O "mysq=yes" -O "mysq_user=user" -O \
        mysql_password="pass"

Perform a dump Job::

    ~/>dardrive dbdump -j myjob


List all the dbdumps available::

     ~/>dardrive show archives -t dbdump -t dbdump.gz
     =================================================================================
        catalog                             type                date            status 
     =================================================================================
     09f376df703a4392978eeb9522c291c6   dbdump        2012-08-27 20:59:50.678357     0
     dfca7690fde74e1e8ed732d0f54dd0da   dbdump.gz     2012-08-27 20:58:46.559500     0


The command show files -c catalog_id will return the locations os the dump
files just as it does with filesystem jobs.


Restoring a database dump
-------------------------

Dardrive does not restores database jobs directly, instead, it outputs the dump
in SQL format to a file or to standard output if the file name is set to "-".

It also tries to decrypt and decompress the archive if the propper options
are set in the current job definition the archive belongs to. 

.. cssclass:: alert alert-error

    **WARNING!** If you change the encryption password of a job after a given
    dump is performed, then dar drive may fail to restore due to bad passwords,
    as it does not store previous passwords. If thats the case, see *manual
    recovery*. It is up to you to store old password information.



In order to oputut the most recent dump of a job to stdout::
    
    dardrive dbrestore -j jobname -f -

Alternativelly you can restore an specific dump::
    
    dardrive dbrestore -i 09f376df703a4392978eeb9522c291c6 -f /tmp/dump.sql
