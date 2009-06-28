#!/bin/sh

Usage()
{
    echo "Usage: ./build-html.sh <wwwdir> <srcdir> <html-header> <html-footer> <db> <treename> <virtroot>"
}

# Cache dir from which script was run so we can get at other scripts later.
SCRIPTDIR=$PWD

if [ -z "$1" ]; then
    Usage
    exit
fi
WWWDIR=$1

if [ -z "$2" ]; then
    Usage
    exit
fi
SRCDIR=$2

if [ -z "$3" ]; then
    Usage
    exit
fi
HTMLHEADER=$3

if [ -z "$4" ]; then
    Usage
    exit
fi
HTMLFOOTER=$4

if [ -z "$5" ]; then
    Usage
    exit
fi
DXRDB=$5

if [ -z "$6" ]; then
    Usage
    exit
fi
TREENAME=$6

if [ -z "7" ]; then
    Usage
    exit
fi
VIRTROOT=$7

cd ${WWWDIR}
cp -R ${SRCDIR}/* ./${TREENAME}-current
rm -fr ./${TREENAME}-current/.hg

# TODO: this could use a lot more parallelization

find ./${TREENAME}-current -name '*.cpp' -exec sh -c "echo {} ; python ${SCRIPTDIR}/cpp2html.py ${HTMLHEADER} ${HTMLFOOTER} ${DXRDB} ./${TREENAME}-current/ {} ${VIRTROOT} ${TREENAME} > {}.html" \; &
find ./${TREENAME}-current -name '*.idl' -exec sh -c "echo {} ; python ${SCRIPTDIR}/idl2html.py ${HTMLHEADER} ${HTMLFOOTER} ${DXRDB} ./${TREENAME}-current/ {} ${VIRTROOT} ${TREENAME} > {}.html" \; &
# NOTE: this will fail on a lot of objective-c .h files due to things like @"...", but can be ignored for now (we don't have dehydra data for obj-c)
find ./${TREENAME}-current -name '*.h' -exec sh -c "echo {} ; python ${SCRIPTDIR}/cpp2html.py ${HTMLHEADER} ${HTMLFOOTER} ${DXRDB} ./${TREENAME}-current/ {} ${VIRTROOT} ${TREENAME} > {}.html" \;
wait

exit 0
