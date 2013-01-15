#!/bin/sh
# Kicks off the Jenkins tests.

echo "Starting jenkins.sh"
ls -alR
/opt/vagrant/bin/vagrant up
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && ls -alR && make test'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
echo "Ending jenkins.sh"
exit $RESULT