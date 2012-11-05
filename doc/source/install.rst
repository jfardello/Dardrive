
Installing
==========

Prerequisites
--------------

* Dar 2.4.X 
* Par2 (par2cmdline) 
* OpenSSL
* Python 2.7, untested on other versions.
* An extended attributes enabled file system.   

.. cssclass:: alert

    If you plan to build par2cmdline from source, note that version 0.4 (2004-04-22)
    has some bugs that may crash par2 while running with -q (quiet mode), get a patched
    version.


Download
--------

The code is hosted at `github <http://github.com/jfardello/Dardrive>`_ .

    
   | ~/>wget \https://github.com/downloads/jfardello/Dardrive/dardrive-|release|.tar.gz\

   | ~/>tar xzf dardrive-|release|.tar.bz2 && cd dardrive-|release|

   | ~/>python setup.py install


