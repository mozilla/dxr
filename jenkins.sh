#!/bin/sh
# Kicks off the Jenkins tests.

VBGUEST=$(vagrant plugin list |grep -i vbguest)
if [ ! "$VBGUEST" ]; then
  vagrant plugin install vagrant-vbguest
fi;

/opt/vagrant/bin/vagrant up --no-provision
sleep 2  # Dodge "SSH connection was refused" errors.

# Try to get ssh not to hang up in the middle of long things like package downloads during provisioning:
vagrant ssh -- '(echo; echo ClientAliveInterval 30; echo ClientAliveCountMax 99999) | sudo tee -a /etc/ssh/sshd_config && service ssh restart'

vagrant provision
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && source /home/vagrant/venv/bin/activate && make clean && make test'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
