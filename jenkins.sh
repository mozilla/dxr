#!/bin/sh
# Kicks off the Jenkins tests.

git submodule sync
git submodule update --init --recursive

/opt/vagrant/bin/vagrant plugin install vagrant-vbguest
/opt/vagrant/bin/vagrant up --no-provision
/opt/vagrant/bin/vagrant halt
/opt/vagrant/bin/vagrant up --provision
echo "DONE PROVISIONING"
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && make clean && make test'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
