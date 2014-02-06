#!/bin/sh
# Kicks off the Jenkins tests.

git submodule sync
git submodule update --init --recursive

/opt/vagrant/bin/vagrant up
echo "DONE PROVISIONING"
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
