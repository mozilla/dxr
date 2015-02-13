#!/bin/sh
# Kicks off the Jenkins tests.

VBGUEST=$(vagrant plugin list |grep -i vbguest)
if [ ! "$VBGUEST" ]; then
  vagrant plugin install vagrant-vbguest
fi;

/opt/vagrant/bin/vagrant up
n=0
until [ $n -ge 5 ]
do
  /opt/vagrant/bin/vagrant ssh -c "echo ok"
  RESULT=$?
  if [ "$RESULT" -eq "0" ]
  then
    break
  fi
  n=$[$n+1]
  sleep 5
done
if [ "$RESULT" -ne "0" ]
then
  exit $RESULT
fi
/opt/vagrant/bin/vagrant ssh -c 'cd /home/vagrant/dxr && make clean && make test'
RESULT=$?
/opt/vagrant/bin/vagrant destroy --force || exit $?
exit $RESULT
