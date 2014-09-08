#!/bin/sh
# Shell script to provision the vagrant box

set -e
set -x

apt-get update
# clean out redundant packages from vagrant base image
apt-get autoremove -y

#configure locales:
apt-get install -y language-pack-en
export LC_ALL="en_US.UTF-8"
locale-gen en_US.UTF-8

# node and npm:
apt-get install -y npm
# Homogenize binary name with production RHEL:
ln -sf /usr/bin/nodejs /usr/local/bin/node

# Docs build system:
apt-get install -y sphinx-common

# Python:
apt-get install -y libapache2-mod-wsgi python-pip
pip install virtualenv virtualenvwrapper python-hglib nose
cd ~vagrant/dxr
./peep.py install -r requirements.txt
python setup.py develop

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
# sqlite3 is so trilite's make test works.
# pkg-config is so make clean works.
apt-get install -y libsqlite3-dev sqlite3 git mercurial llvm-3.3 libclang-3.3-dev clang-3.3 pkg-config
update-alternatives --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.3 0
# Install libtrilite so Apache WSGI processes can see it:
ln -sf ~vagrant/dxr/trilite/libtrilite.so /usr/local/lib/libtrilite.so
# make sure local trilite is available
rm /etc/ld.so.cache
/sbin/ldconfig
