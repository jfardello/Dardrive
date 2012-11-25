Usage
=====

Creating a profile
------------------

In order to run, dardrive needs a directory in the user's home that holds jobs
configuration, dar_manager databases, and various settings. 
The user configuration directory is created by the init command. ::

    ~/>dardrive init
    Config file written.
    Settings file written.

This will place some files in the ~/.dardrive directory, now you can edit
``~/.dardrive/jobs.cfg``, or alternatively modify it via the addjob and modjob
commands. 

Config directory contents:

    setts.py           
        Here you can specify database settings (see `SQLAlchemy engines`_).

    jobs.cfg           
        The Jobs config file, it has an ini-file style, with mandatory [global]      
        he Jobs config file, it has an ini-file style, with mandatory [global]       
        section which holds all the defaults. Each extra section represents a        
        backup job, which should have at least a root option defined. Lines          
        beginning with a dash ("#") or a semicolon (;) are considered comments.      

    dardrive.db
        The default the SA backend.                    
    
    dmd/<jobname>.dmd
        Per job dar_manager database.

.. _`SQLAlchemy engines`: http://docs.sqlalchemy.org/en/rel_0_7/core/engines.html



Adding jobs
-----------

.. code-block:: sh 
    
    ~/>dardrive addjob projects -R /home/user/projects -A /mnt/bkp/arch \
        -C /mnt/bkp/cat
    Job added
    ~/>dardrive modjob -j projects -O 'compr=yes' -O 'par=yes'
    Job modified

This will place a ``[projects]`` section in the ini style config file
``~/.dardrive/jobs.cfg``, with ``compr`` and ``par`` options set to yes.


Running a filesystem backup
---------------------------

.. code-block:: sh 

    ~/>dardrive backup -j projects 
    job status:      successful
    time took:       00:01:12
    job id:          003r005938r2we010181173f5w23   
    ~/>


The backup command  produces a series of files in the catalog_store and the
archive_store; archive files will be placed in <<archive_store>>/projects/ and
catalogs inside  <<catalog_store>>/projects/. 

.. cssclass:: alert alert-warning

    | **Warning**
    | Note that dardrive places a pid-lock that prevents running **backup**,
      **dbdump**, **import** and **rebuild_dmd** commands on the same job and
      host at the same time.

Listing archives, jobs, files and logs
--------------------------------------
Listing operations are done by the show command, most of them can be filtered by the 
-j, -n, -i, and -t switches, which filter by job, entries, jobid (an specific backup task.)
and backup type respectively. Optionally the "show files" commands can be modified by the -b, which 
will strip the "slice.extension" part of a backup, suitable for feeding dar commands.

Examples: 

    get last 3 bases of the projects job::
    
        ~/> dardrive show archives -j projects -n 3 

    show the log for the last run of myjob::

        ~/> dardrive show log -j myjob -n 1

    show the log for the ``003r005938r2we010181173f5w23`` jobid::

        ~/> dardrive show log -i 003r005938r2we010181173f5w23

    copy the files involved in the last full filesystem backup for the documents job::

        ~/> for file in `dardrive show files -t Full -j documents -n 1`; do \
                cp $file /mnt/usb ;done 



Recovering files
----------------

Recovery operations restores files to the recover_path location, in order to
recover from the leatest archive::

    dardrive recover -f myfile.png -j docs

To recover specific versions a date string in dar's format must be passed with
the ``-w`` switch, dardrive creates those strings with the versions command::

    dardrive versions -j docs -f myfile.rst 
    2012/10/15-14:08:16
    2012/10/18-12:16:59
    dardrive recover -j docs -f myfile.rst -w "2012/10/18-12:16:59" 

Note that:
    * dardrive will restore files or directory trees.
    * dardrive will add a second to the date string because of the dar_manager
      logic which restores the latest file before this date.
    * a changed inode (in the case of directories) does not explicitly means a
      change on its contents. 

Getting statistics
------------------

Stats are saved for each successfull job, which means dar status 0 and 11, and
they persist backup rotation.

They can be globaly reseted whith the `reset_stats` command, and displayed by the `show
stats` command, which may be filtered by job.


Email Integration
-----------------
Email reporting is disabled by default, you can enable it by modifying the jobs's 
``send_email`` and ``report_success`` options ::

    >dardrive modjob -j docs -O "send_email=yes" -O "smtp_server=smtp.gmail.com:587"
    >dardrive modjob -j docs -O "smtp_user=username@gmail.com" -O smtp_pass="secret" 
    >dardrive modjob -j docs -O "subject=Backup for Docs report"

The smtp server is defined in the smtp_server option and it defaults to localhost.
If the port is not specified (appending a semicolon and the port), port 25 is
assumed, also if the port is set to 587, STARTTLS will be used with the
``smtp_user`` and ``smtp_pass`` options.


Encryption
----------

Fs backup may be encrypted, there's an option for passing encryption
information to dar ::

    >dardrive modjob -j docs -O "encryption=aes:secret"

Although that the previous example will make it, the prefferable way is to leave 
the password blank and provide one. This method will raise an error if dardrive is
not running on a tty, ie inside a shell script. ::

    >dardrive modjob -j docs -O "encryption=aes:"
      Please provide a password for the docs job:
      Password: *********** 

This will create a temporary file on runtime that will be read by dar via the "--batch"
switch.

When running a database dump, just the ":password" part is relevant as dbdumps
are always encrypted with OpenSSL's aes-cbc 256 cipher.


Parity
------

Par2 error correction files are generated after each slice is created if the 
``redundancy`` option is an integer between 1-100 which is the percent of
redundancy saved. It can be disabled with the "0" value. ::  

    >dardrive modjob -j docs -O "redundancy=0"

Dardrive will generate parity files on the "local_store" by default, and move the
file and the archives before creating a new slice. In order to generate the
files on the final destination, i.e.: archive_store is a local filesystem or it
is fast enough, you can disable the ``par_local`` boolean option. ::

    >dardrive modjob -j docs -O "par_local=no"

Alternatively you can build parity files for individual and previously created files
after enabling redundancy::

    >dardrive modjob -j docs -O "redundancy=5"
    >dardrive parity create -i 0dc2597de4cf421fa038197242adb94d


Importing an archive store
--------------------------

Dardrive is server-less, even though the database can be centralized, there's
no need for that as dardrive saves all the data it needs as extended attributes
on the first slice of an archive file. The only advantage on centralizing the
database is to preserve logs. That being said, an archive_store can be imported
into other machines just by defining a job pointing to it and being able to
access that filesystem. ::

    >dardrive addjob srvstuff -R /srv/stuff -A /mnt/bkp/arch -C /var/cat
    >dardrive modjob -j srvstuff -O "catalog_begin=2010-01-01"
    >dardrive import -j srvstuff

.. cssclass:: alert alert-warning

    **Warning:** If dardrive can't access the corresponding catalogs from the
    catalog_store, it will isolate a new one, on slow & "no-lseekable" media it
    this will be a long-lasting operation, and sometimes even expensive, in order
    to prevent that you should define the catalog_begin option for that job.  

