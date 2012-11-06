
Manual recovery
===============

**Just in the case that dardrive is not available**, archives can be  manually 
restored as they are essentially dar or mysql_dump files. You'll need the
``dar``, ``gzip``, ``par2`` and ``openssl`` commands. 
Please read dar's docs `here`_, this page is just quick introduction to dar.

.. _`here`: http://dar.linux.free.fr/doc


Listing dar archive content
---------------------------

Theres no difference in listing file contents from archives or from isolated
catalog files, assuming that /mnt/bkp/arch is dardrive's archive_store and
/mnt/bkp/cat the catalog_store::

    >dar -l /mnt/bkp/arch/home/8af5b24a77ff4b0ea5bd21fc62c02e4b
    >dar -l /mnt/bkp/cat/home/8af5b24a77ff4b0ea5bd21fc62c02e4b

Note that most dar commands will expect a "dar_base" as argument, which is the
file name  without the trailing slice and extension.


Restoring files with dar
------------------------

When restoring an archive dar will pull the content of all reference archives if
it is restoring a differential backup, so in practice full and differential backups are
restored the same way.

In order to restore all files to the ``/output`` directory::

    >dar -x archive_base -R /output 


Restoring just some files::

    >dar -R /output -x archive_base -g files/to/recover

Please take a look at the dar_manager man page, if you have access to the
".dardrive" directory of the user that runs the backups, you may take advantage of the
per job dar_manager database that dardrive mantains there. 
(``~user/.dardrive/dmds/jobname.dmd``)


Mysql restoring
---------------

Mysql backups are plain sql files that can be optionally encrypted, and compressed,
you can guess that information from the job.cfg file, but an old backup could
be produced with a different version of that cfg file.
You can get information on how a backup was produced by examining the first
slice's extended attributes::
    
    >getfattr <filename>.dmp.gz | grep enc
    getfattr: Removing leading '/' from absolute path names
    user.dardrive.enc="True"

The encryption for bd dumps is openssl's aes cbc 256, and the  commpression can be
deduced by the file extension, in this case::

    >zcat <filename>.dmp.gz | openssl enc -d -aes-256-cbc > file.out


