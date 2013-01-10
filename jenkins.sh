#!/bin/sh -e
# Kicks off the Jenkins tests.

/opt/vagrant/bin/vagrant up
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && make test'
# Should we explicitly destroy the vagrant box here?
