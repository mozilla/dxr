Downloading DXR
===============

Using git, clone the DXR repository::

   git clone https://github.com/mozilla/dxr.git


Booting And Building
====================

DXR runs only on Linux at the moment (and possibly other UNIX-like operating
systems). The easiest way to get things set up is to use the included,
preconfigured Docker setup. If you're not running Linux on your host machine,
you'll need a virtualization provider. We recommend VirtualBox.

After you've installed VirtualBox (or ignored that bit because you're on
Linux), grab the three Docker tools you'll need: docker, docker-compose, and,
if you're not on Linux, docker-machine. If you're running the homebrew package
manager on the Mac, this is as easy as... ::

    brew install docker docker-compose docker-machine

Otherwise, visit the `Docker Engine
<https://docs.docker.com/engine/installation/>`_ page for instructions.

Next, unless you're already on Linux, you'll need to spin up a Linux VM to
host your Docker containers::

    docker-machine create --driver virtualbox --virtualbox-disk-size 50000 --virtualbox-cpu-count 2 --virtualbox-memory 512 default
    eval "$(docker-machine env default)"

Feel free to adjust the resource allocation numbers above as you see fit.

.. note::

    Next time you reboot (or run ``make docker_stop``), you'll need to restart
    the VM::

        docker-machine start default

    And each time you use a new shell, you'll need to set the environment
    variables that tell Docker how to find the VM::

        eval "$(docker-machine env default)"

    When you're done with DXR and want to reclaim the RAM taken by the VM,
    run... ::

        make docker_stop

Now you're ready to fire up DXR's Docker containers, one to run elasticsearch
and the other to interact with you, index code, and serve web requests::

    make shell

This drops you at a shell prompt in the interactive container. Now you can
build DXR and run the tests to make sure it works. Type this at the prompt
*within the container*::

    # Within the docker container...
    make test
