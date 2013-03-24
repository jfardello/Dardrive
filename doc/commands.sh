#!/bin/bash



for comm in $(dardrive help | tail -n +4 - | tr " " "\n" | sort | uniq | tail -n +2 - ) ; do 
    echo -e "\n\n${comm}"
    echo `seq -s_ $((${#comm}+2))|tr -d '[:digit:]'` 
    echo -e "\n"
    echo -e "::\n\n"
    dardrive help $comm | awk '{print "    " $0}' 
    echo -e "\n\n"
done  >> source/dar_commands.rst

