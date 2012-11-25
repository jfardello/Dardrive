#!/bin/bash



for comm in $(dardrive help | tail +4 | tr " " "\n" | sort | uniq | tail +2) ; do 
    echo -e "\n\n${comm}:"
    echo `seq -s_ $((${#comm}+2))|tr -d '[:digit:]'` 
    echo -e "\n"
    dardrive help $comm 
done >> source/dar_commands.rst

