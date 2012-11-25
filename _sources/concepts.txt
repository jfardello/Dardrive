
Basic concepts
==============

File types
----------

Dardrive stores backups and catalogs as .dar files, in the ``archive_store``
and ``catalog_store`` respectively. The first slice for each individual catalog
will be saved with extended attributes on which dardrive represents the
metadata needed to import an archive store on another system.    


Jobs
----

Backup Jobs are definitions within the main config file, which define the
storage and backup paths, and a series of properties such as compression,
encryption, rotation, etc.


Backup types
------------

Dardrive may produce 4 different kinds of backups for a given job:

**Full filesystem backup,** are dar backups with root path specified with the
``root`` option, all the files are stored in one or more slices of the same dar
base. They are produced either forcing a full backup or when the last full is
olther than the maximum age in days allowed for a job (specified by the
``diffdays`` option).

**Incremental filesystem backups** are dar archives which saves only files that
have changed since reference full backup. Dardrive uses as a reference a catalog
file corresponding with the last full backup for a given job.

**Database dumps** are simple mysqldump files of a given database or a
collection of databases in SQL format. 

**Gzipped database dumps** are gzipped versions of database dumps.

Additionally, all kinds of backups can be encrypted, file system ones
use dar's internal encryption, database dumps use openssl symmetric
encryption.


When dardrive runs a filesystem backup several actions take place:

   | 1. It chooses whether to run an incremental or full backup.
   | 2. It creates an entry on its internal database.
   | 3. Runs the dar backup and builds parity files if configured,
        also if the par_local option is.
   | 5. Save metadata as extended attributes of the first slice of the archive.
   | 7. Appends the logs from previous operations to the database.
   | 8. Adds the catalog from the backup to a dar_manager database.
   | 9. Run the rotation algorithm, which may modify the database,
        delete old archives, and update extended attributes of previous archives.
