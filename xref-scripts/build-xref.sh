#!/bin/sh

Usage()
{
    echo "Usage: ./build-xref.sh <objdir> <xrefscripts> <dbdir> <dbname> <wwwdir> <treename>"
}

if [ -z "$1" ]; then
    Usage
    exit
fi
OBJDIR=$1

if [ -z "$2" ]; then
    Usage
    exit
fi
DXRSCRIPTS=$2

if [ -z "$3" ]; then
    Usage
    exit
fi
DBROOT=$3

if [ -z "$4" ]; then
    Usage
    exit
fi
DBNAME=$4

if [ -z "$5" ]; then
    Usage
    exit
fi
WWWDIR=$5

if [ -z "$6" ]; then
    Usage
    exit
fi
TREENAME=$6

# backup current data while we build new
if [ -d ${WWWDIR}/${TREENAME}-current ]
then
    # See if last build/index was successful
    if [ ! -e ${WWWDIR}/${TREENAME}-current/.dxr_xref/.success ]
    then 
      # Leave the existing -old index in place and try again (failed build)
      rm -fr ${WWWDIR}/${TREENAME}-current	
    else 
      # Backup the existing so the web app still works while we build the new one
      rm -fr ${WWWDIR}/${TREENAME}-old
      mv ${WWWDIR}/${TREENAME}-current ${WWWDIR}/${TREENAME}-old
      rm -f ${WWWDIR}/${TREENAME} # symlink to -current
      ln -s ${WWWDIR}/${TREENAME}-old ${WWWDIR}/${TREENAME}
    fi
fi

mkdir ${WWWDIR}/${TREENAME}-current

# create dir to hold db if not present
if [ ! -d ${DBROOT} ]; then mkdir ${DBROOT}; fi

cd ${DBROOT}

# merge and de-dupe sql scripts, putting inserts first, feed into sqlite
echo "Post-process all C++ .sql and create db..."
find ${OBJDIR} -name '*.sql' -exec cat {} \; > ${DBROOT}/all.sql
echo 'PRAGMA journal_mode=off; PRAGMA locking_mode=EXCLUSIVE; BEGIN TRANSACTION;' > ${DBROOT}/all-cpp.sql
cat ${DXRSCRIPTS}/dxr-schema.sql >> ${DBROOT}/all-cpp.sql
echo 'COMMIT; PRAGMA locking_mode=NORMAL;' >> ${DBROOT}/all-cpp.sql
echo 'PRAGMA journal_mode=off; PRAGMA locking_mode=EXCLUSIVE; BEGIN TRANSACTION;' >> ${DBROOT}/all-cpp.sql
awk '!($0 in a) {a[$0];print}' ${DBROOT}/all.sql >> ${DBROOT}/all-cpp.sql
echo 'COMMIT; PRAGMA locking_mode=NORMAL;' >> ${DBROOT}/all-cpp.sql
rm ${DBROOT}/all.sql

sqlite3 ${DBROOT}/${DBNAME} < ${DBROOT}/all-cpp.sql > ${DBROOT}/error-cpp.log 2>&1
# XXX: leaving this file for debugging
#rm ${DBROOT}/all-cpp.sql
echo "DB built."

# Defrag db
sqlite3 ${DBNAME} "VACUUM;"

# Everything worked, log success
touch ${DBROOT}/.success

echo "Done - DB created at ${DBROOT}/${DBNAME}"
