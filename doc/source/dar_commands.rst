Dardrive Commands
=================


**addjob** 

Adds a job definition. ::

    usage: addjob [-h] -R ROOT -A ARCHIVE_STORE [-C CATALOG_STORE] jobname
    
    positional arguments:
      jobname               Job name
    
    optional arguments:
      -h, --help            show this help message and exit
      -R ROOT, --root ROOT  Job root path
      -A ARCHIVE_STORE, --archive-store ARCHIVE_STORE
                            archive store
      -C CATALOG_STORE, --catalog-store CATALOG_STORE
                               catalog store


**backup**

Perform a backup task. ::

    usage: backup [-h] -j JOB [-v] [-R ROOT] [-f]
    
    optional arguments:
      -h, --help            show this help message and exit
      -j JOB, --job JOB     Backup job
      -v, --verbose         Verbose output
      -R ROOT, --root ROOT  Override bkp root path.
      -f, --full            Force a full backup
    
**dbdump**

Run an mysql backup job. ::

    usage: dbdump [-h] -j JOB
    
    optional arguments:
      -h, --help         show this help message and exit
      -j JOB, --job JOB  Backup job
    
**dbrecover**

Load a db backups to file or stdout, decrypting and uncompressing as needed. ::

    usage: dbrecover [-h] [-i ID] [-j JOB] filename
    
    positional arguments:
      filename           output filename ("-" for stdout)
    
    optional arguments:
      -h, --help         show this help message and exit
      -i ID, --id ID     Limit operation to specified backup id.
      -j JOB, --job JOB  Limit operation to jobname
    
**import**

Import an untracked job to db. ::

    usage: import [-h] -j JOB
    
    optional arguments:
      -h, --help         show this help message and exit
      -j JOB, --job JOB  Specifies the job

    
**init**

Inits the userconfig directory

    
**modjob**

Modifies any job section option. ::

    Modifies any job section option.
    usage: modjob [-h] -j JOB -O OPTION
    
    optional arguments:
      -h, --help            show this help message and exit
      -j JOB, --job JOB     Job being modified
      -O OPTION, --option OPTION
                            config string
    
**parity**

Generates "par2" error correction files. ::

    usage: parity [-h] -i ID {create,test}
    
    positional arguments:
      {create,test}
    
    optional arguments:
      -h, --help      show this help message and exit
      -i ID, --id ID  Specifies the jobid.
    
**quit**

Quits the dardrive interpreter if in interactive mode.

**rebuild_dmd**

Re-creates the dmd for a given job. ::

    Re-creates the dmd for a given job.
    usage: rebuild_dmd [-h] -j JOB
    
    optional arguments:
      -h, --help         show this help message and exit
      -j JOB, --job JOB  Specifies the job name.
    
**recover**

Recover files through dar_manager. ::

    usage: recover [-h] -f FILE -j JOB [-r RPATH] [-w WHEN]
    
    optional arguments:
      -h, --help            show this help message and exit
      -f FILE, --file FILE  File to search for
      -j JOB, --job JOB     Specifies the job
      -r RPATH, --rpath RPATH
                            Recover path
      -w WHEN, --when WHEN  Before date (in dar_managet format)
    
**show**

Shows various listings. ::

    usage: show [-h] [-l] [-j JOB] [-i ID] [-b] [-n NUM] [-t TYPE] {jobs,logs,archives,files}
    
    positional arguments:
      {jobs,logs,archives,files}
    
    optional arguments:
      -h, --help            show this help message and exit
      -l, --long            Show job details.
      -j JOB, --job JOB     Filter by job
      -i ID, --id ID        Filter by id
      -b, --base            When showing files, show only dar archive base (excluding isolated catalogs)
      -n NUM, --num NUM     Limit number of log|archives entries
      -t TYPE, --type TYPE  filter by type
    
**stats**

Show job statistics. ::

    usage: stats [-h] [-j JOB]
    
    optional arguments:
      -h, --help         show this help message and exit
      -j JOB, --job JOB  Show stats for job


**versions** 

Show available copies of a given file. ::

    usage: versions [-h] -f FILE -j JOB
    
    optional arguments:
      -h, --help            show this help message and exit
      -f FILE, --file FILE  File to search for
      -j JOB, --job JOB     Specifies the job
    