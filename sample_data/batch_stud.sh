#!/bin/bash

#Stub script to be converted to a job array 
#DIRECTORY=$1 

# -- SGE options (whose lines must begin with #$)

#$ -S /bin/bash       # Our jobscript is written for the bash shell
#$ -V                 # Inherit environment settings (e.g., from loaded modulefiles)
#$ -cwd               # Run the job in the current directory
#$ -pe smp.pe 4       # Example: 2 cores. Can specify 2-16. Do NOT use 1.
                      # Comment above line out for one core  

DIRECTORY=$1

# Go in to the directory
cd $DIRECTORY

#Get the link(s) to a file(s)
the_link=$(cat "data.link")

#Do something (more) useful with the link(s)
cp the_link local_copy.txt
