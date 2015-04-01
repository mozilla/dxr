Downloading DXR
===============

Using git, clone the DXR repository::

   git clone --recursive https://github.com/mozilla/dxr.git

Remember the :option:`--recursive` option; DXR depends on the `TriLite SQLite
extension`_, which is included in the repository as a git submodule.


Booting And Building
====================


Vagrant Environment
-------------------

DXR runs only on Linux at the moment (and possibly other UNIX-like operating
systems). The easiest way to get things set up is to use the included,
preconfigured Vagrant_ VM. You'll need Vagrant and a virtualization provider
for it. We recommend VirtualBox.

Once you've installed VirtualBox and Vagrant, run these commands in DXR's
top-level directory::

   vagrant plugin install vagrant-vbguest
   vagrant up
   vagrant ssh

Then, run this inside the VM::

   cd ~/dxr
   make

.. note::

   The Vagrant image is built for VirtualBox 4.2.0 or newer.  If your version is older,
   the image might not work as expected.

   Your Vagrant version may require a specific vbguest plugin installation method.
   If you receive errors about the plugin visit the vbguest_ plugin page.

Docker environment
------------------

To work effectively using an IDE of choice on Windows or OSX outside the docker container,
a number of preparatory steps need to be completed to enable a seamless workflow between
environments. You are of course more than welcome to do all your edits and git commits in
the docker container. However, this setup is uncommon and may restrict your workflow if you
are not intimately familiar with command line based editors, git commands, and docker image
management.

Linux Users
###########

Getting DXR running in Docker is relatively straightforward. Follow the `instructions`_ for your
distribution. Then do the following in a terminal:

1. cd to wherever you cloned the dxr.git repository

2. Run `docker build .`

3. Once the build completes, run `docker run -i -p 8000:8000 $(docker images -q|head -n1) /bin/bash`

Windows Users
#############

For those who choose to develop on Windows hosts, follow the Docker `Windows Installation guide`_.
Once you have successfully run the `hello-world` test shown on that page, you must now
install a custom boot2docker ISO image to enable Shared Folders between your Windows system,
the boot2docker VirtualBox guest environment, and the Docker container hosted in the guest VM.

1. Stop boot2docker. In a terminal run: `boot2docker stop`

2. Navigate to `C:\Users\user.name\.boot2docker` (where user.name is where you find your
 user's files and settings)

3. Rename the `boot2docker.iso` file to `boot2docker.iso.original` for safekeeping.

4. Download the unofficial `boot2docker.iso`_ file with the guest additions already enabled and
save it to your `.boot2docker` directory.

5. Make a note of where you cloned `dxr.git`. If you put it on your Desktop the path would be 
something like `C:\Users\user.name\Desktop\dxr`.

6. Now map the shared folder. In a terminal run:
`"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" sharedfolder add boot2docker-vm -name home -hostpath C:\Users\user.name\Desktop\dxr` where the final path in that command is the location of
the DXR codebase that you noted in Step 5. This command makes your DXR codebase show up in
the boot2docker VM under /Users.

7. Now run your boot2docker Start script from the desktop, or `boot2docker start` in a terminal.

8. cd to `/Users` in the boot2docker terminal and run `docker build .`


OSX Users
#########

For those who choose to develop on OSX hosts, follow the Docker `OSX Installation guide`_.
Once you have successfully run the `hello-world` test shown on that page, you must now
install a custom boot2docker ISO image to enable Shared Folders between your OSX system,
the boot2docker VirtualBox guest environment, and the Docker container hosted in the guest VM.

1. Stop boot2docker. In a terminal run: `boot2docker stop`

2. Navigate to `~/.boot2docker`

3. Rename the `boot2docker.iso` file to `boot2docker.iso.original` for safekeeping.

4. Download the unofficial `boot2docker.iso`_ file with the guest additions already enabled and
save it to your `.boot2docker` directory.

5. Make a note of where you cloned `dxr.git`. If you put it on your Desktop the path would be 
something like `~/Desktop/dxr`, Documents would be `~/Documents/dxr` and so on.

6. Now map the shared folder. In a terminal run:
`VBoxManage sharedfolder add boot2docker-vm -name home -hostpath ~/Desktop/dxr` where the final
path in that command is the location of the DXR codebase that you noted in Step 5. This command
makes your DXR codebase show up in the boot2docker VM under /Users.

7. Now run your boot2docker Start script from the desktop, or `boot2docker start` in a terminal.

8. Run the export `DOCKER_HOST=...` command to make the TCP address available for docker.

9. cd to your dxr codebase that you noted in Step 5 and run `docker build .`

10. Run `docker run -i -t $(docker images -q |head -n 1) --net=host -v /Users:/dxr /bin/bash` to
start up the docker container and enter into it. Code lives in the /dxr directory.

11. Build and run DXR with the usual make & make test commands

12. To browse a running dxr-serve.py instance, visit the address returned by the following:
`echo $DOCKER_HOST| sed -e 's/tcp/http/' -e 's/:2375/:8000/'`

.. _TriLite SQLite extension: https://github.com/jonasfj/trilite

.. _Vagrant: http://www.vagrantup.com/

.. _vbguest: https://github.com/dotless-de/vagrant-vbguest

.. _installation: https://docs.docker.com/installation

.. _Windows Installation guide: https://docs.docker.com/installation/windows

.. _boot2docker.iso: http://static.dockerfiles.io/boot2docker-v1.1.2-virtualbox-guest-additions-v4.3.12.iso
