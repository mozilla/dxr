#!/bin/sh
# Kicks off the Jenkins tests.

git submodule sync
git submodule update --init --recursive

VBGUEST=$(vagrant plugin list |grep -i vbguest)
if [ ! "$VBGUEST" ]; then
  vagrant plugin install vagrant-vbguest
fi;

/opt/vagrant/bin/vagrant box remove ubuntu/trusty64 vagrant -f

/opt/vagrant/bin/vagrant up
/opt/vagrant/bin/vagrant ssh -c 'sudo adduser vagrant docker'
/opt/vagrant/bin/vagrant ssh -c '/bin/bash /home/vagrant/dxr/docker-build.sh'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
