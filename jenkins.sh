#!/bin/sh
# Kicks off the Jenkins tests.

git submodule sync
git submodule update --init --recursive

vagrant box remove trusty64

VBGUEST=$(vagrant plugin list |grep -i vbguest)
if [ ! "$VBGUEST" ]; then
  vagrant plugin install vagrant-vbguest
fi;

/opt/vagrant/bin/vagrant up
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && make clean && make test'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
