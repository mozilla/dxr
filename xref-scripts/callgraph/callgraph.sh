#!/bin/sh

# check args
if test $# -ne 2; then
  echo "usage: $0 /path/to/gcc /path/to/dehydra"; exit 1;
elif test ! -d $1; then
  echo "gcc path $1 invalid (require path to gcc and g++ with plugin support)"; exit 1;
elif test ! -d $2; then
  echo "dehydra path $2 invalid (require path to gcc_treehydra.so)"; exit 1;
fi

# determine callgraph root path
cd `dirname $0`;
SCRIPTROOT=`pwd`;
cd - > /dev/null;

# paths used by this script
MOZCENTRAL=${SCRIPTROOT}/mozilla-central/
#SOURCEROOT=${MOZCENTRAL}/mozilla
SOURCEROOT=${MOZCENTRAL}
OBJDIR=${MOZCENTRAL}/obj-fx
DISTBIN=${OBJDIR}/dist/bin
DBROOT=${SCRIPTROOT}/db
DBBACKUP=${SCRIPTROOT}/db-backup

# variables exported for use by the build
export GCCBIN=$1
export DEHYDRA=$2
export SCRIPT=${SCRIPTROOT}/callgraph_static.js
export MOZCONFIG=${SCRIPTROOT}/mozconfig
export OBJDIR=${OBJDIR}

# check we have a tree
if test ! -d "${SOURCEROOT}"; then
  echo "$0: source tree not found. pulling...";
  mkdir ${MOZCENTRAL}
  cd ${MOZCENTRAL}
  if ! eval "hg clone http://hg.mozilla.org/mozilla-central mozilla"; then
    echo "$0: checkout failed"; exit 1;
  fi
fi

# clobber build
cd ${SOURCEROOT}
rm -rf ${OBJDIR}

# build the tree
echo "$0: building...";
if ! eval "make -s -f client.mk build"; then
  echo "$0: build failed"; exit 1;
fi

# move old db and sql scripts
rm -rf ${DBBACKUP}
mv ${DBROOT} ${DBBACKUP}
mkdir ${DBROOT}
cd ${DBROOT}

# merge and de-dupe sql scripts, feed into sqlite
echo "$0: generating database...";
(cat ${SCRIPTROOT}/schema.sql
echo 'BEGIN TRANSACTION;'
#find ${OBJDIR} -name '*.sql' -exec ${SCRIPTROOT}/fix_paths.pl ${SOURCEROOT} ${OBJDIR} {} \;|sort -u
find ${OBJDIR} -name '*.sql' | xargs cat
cat ${SCRIPTROOT}/indices.sql
echo 'COMMIT;') > all.sql
if ! eval "sqlite3 graph.sqlite < all.sql > error.log"; then
  echo "$0: sqlite3 db generation failed"; exit 1;
fi

# generate dot file from edges
#${DISTBIN}/run-mozilla.sh ${DISTBIN}/xpcshell -v 180 ${SCRIPTROOT}/sqltodot.js ${DBROOT}/graph.sqlite ${DBROOT}/graph.dot ${MOZCENTRAL}
#dot -v -Tsvg -o ${DBROOT}/graph.svg ${DBROOT}/graph.dot

