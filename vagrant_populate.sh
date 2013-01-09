#!/bin/sh -e
# Copies the DXR checkout to the Vagrant VM. This is necessary only until we
# get VirtualBox shared folders working on the Jenkins hosts.

# TODO: Omit the .git directory for speed.

vagrant ssh-config > .vagrant_ssh_config
scp -r -F .vagrant_ssh_config . default:dxr_for_jenkins
rm .vagrant_ssh_config
