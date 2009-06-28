#!/bin/sh

# Create glimpse index of source files (cpp, h, and idl for now).  Should be done last!

Usage()
{
    echo "Usage: ./build-glimpseidx.sh <wwwdir> <treename> <idxdir> <glimpseindex>"
}

if [ -z "$1" ]; then
    Usage
    exit
fi
WWWDIR=$1

if [ -z "$2" ]; then
    Usage
    exit
fi
TREENAME=$2

if [ -z "$3" ]; then
    Usage
    exit
fi
IDXDIR=$3

if [ -z "$4" ]; then
    Usage
    exit
fi
GLIMPSEINDEX=$4

# Steal the symlink from -old to -current
cd ${WWWDIR}
rm -f ${TREENAME}
ln -s ${TREENAME}-current ${TREENAME}

# Find all .cpp, .h, and .idl (note: files are mixed with .html, so using -F to pass on stdin)
find -H ${WWWDIR}/${TREENAME} -name '*.cpp' -o -name '*.h' -o -name '*.idl' | ${GLIMPSEINDEX} -H ${IDXDIR} -F
cd ${IDXDIR}
chmod 644 .g*
