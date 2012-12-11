class apache {
    package { "apache2-dev":
        ensure => present,
        before => File['/etc/apache2/sites-enabled/dxr.conf'];
    }

    file { "/etc/apache2/sites-enabled/dxr.conf":
        source => "$PROJ_DIR/puppet/files/etc/httpd/conf.d/dxr.conf",
        owner => "root", group => "root", mode => 0644,
        require => [
            Package['apache2-dev']
        ];
    }

    exec {
        'a2enmod rewrite':
        onlyif => 'test ! -e /etc/apache2/mods-enabled/rewrite.load';
        'a2enmod proxy':
        onlyif => 'test ! -e /etc/apache2/mods-enabled/proxy.load';
    }

    service { "apache2":
        ensure => running,
        enable => true,
        require => [
            Package['apache2-dev'],
            File['/etc/apache2/sites-enabled/dxr.conf']
        ];
    }
}
