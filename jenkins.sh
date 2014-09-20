#!/bin/sh
# Kicks off the Jenkins tests.

git submodule sync
git submodule update --init --recursive

VBGUEST=$(vagrant plugin list |grep -i vbguest)
if [ ! "$VBGUEST" ]; then
  vagrant plugin install vagrant-vbguest
fi;

/opt/vagrant/bin/vagrant up
/opt/vagrant/bin/vagrant ssh -c 'sudo adduser vagrant docker'
/opt/vagrant/bin/vagrant ssh -c 'cd dxr; docker build .; docker run -i -t -v $PWD:/dxr $(docker images -q |head -n 1) /bin/bash /dxr/build.sh'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
