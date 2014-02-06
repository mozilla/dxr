#!/bin/sh
# Shell script to provision the vagrant box

set -e
set -x

apt-get update

# node and npm:
apt-get install -y npm
# Homogenize binary name with production RHEL:
ln -sf /usr/bin/nodejs /usr/local/bin/node

# Python:
apt-get install -y libapache2-mod-wsgi python-pip
pip install virtualenv virtualenvwrapper python-hglib nose
cd ~vagrant/dxr
# If it hangs here, you might have a mismatched version of the VirtualBox Guest
# Additions. Shut down the box. Start it back up using the VB GUI. Choose
# "Insert Guest Additions CD" from the Devices menu. On the guest, mount
# /dev/cdrom /mnt && cd /mnt && ./VBoxLinuxAdditions.run. Shut the guest back
# down.
pip install --no-deps -r requirements.txt
python setup.py develop &> setup-develop.log || echo "Done with setup.py develop, rain or shine."
cat setup-develop.log

# Apache:
apt-get install -y apache2-dev apache2
mkdir -p /etc/apache2/sites-enabled
if [ ! -e /etc/apache2/sites-enabled/dxr.conf ]; then
    cat >/etc/apache2/sites-enabled/dxr.conf <<THEEND
# This is an example of serving a DXR target directory with Apache. To try it
# out, go into tests/test_basic and run "make". Everything but a few static
# files is delegated to a WSGI process.
#
# This should be adaptable to serve at non-root positions in the URL hierarchy.

# IF EDITING THIS ON YOUR HOST MACHINE, remember to "vagrant provision" so the
# VM sees it.

<VirtualHost *:80>
    # Serve static resources, like CSS and images, with plain Apache:
    Alias /static/ /home/vagrant/dxr/dxr/static/

    # We used to make special efforts to also serve the static pages of
    # HTML-formatted source code from the tree via plain Apache, but that
    # tangle of RewriteRules saved us only about 20ms per request. You can do
    # it if you're on a woefully underpowered machine, but I'm not maintaining
    # it.

    # Tell this instance of DXR where its target folder is:
    SetEnv DXR_FOLDER /home/vagrant/dxr/tests/test_basic/target/

    # On a production machine, you'd typically do "python setup.py install"
    # rather than "python setup.py develop", so this would point inside your
    # site-packages directory.
    WSGIScriptAlias / /home/vagrant/dxr/dxr/dxr.wsgi
</VirtualHost>
THEEND
    chmod 0644 /etc/apache2/sites-enabled/dxr.conf
fi
a2enmod rewrite
a2enmod proxy
a2dissite 000-default

# DXR itself:
apt-get install -y libsqlite3-dev git mercurial llvm-3.3 libclang-3.3-dev clang-3.3 pkg-config
ln -sf /usr/bin/llvm-config-3.3 /usr/local/bin/llvm-config
# Install libtrilite so Apache WSGI processes can see it:
ln -sf ~vagrant/dxr/trilite/libtrilite.so /usr/local/lib/libtrilite.so
/sbin/ldconfig

make clean
make test
