class webapp::dxr {

    package {
        [
          'libsqlite3-dev',
          'git',
          'mercurial',
          'llvm-3.3',
          'libclang-3.3-dev',
          'clang-3.3',
          'pkg-config',
          'apache2-dev',
          'apache2',
          'libapache2-mod-wsgi',
          'python-pip',
          'npm',
        ]:
        ensure => installed,
    }

    exec { "homogenize-with-RHEL":
        command => "/bin/ln -sf /usr/bin/nodejs /usr/local/bin/node",
        require => Package["npm"]
    }

    exec { "link-llvm-config":
        command => "/bin/ln -sf /usr/bin/llvm-config-3.3 /usr/local/bin/llvm-config",
        require => Package["llvm-3.3"]
    }

    exec { "link-libtrilite":
        command => "/bin/ln -sf /home/vagrant/dxr/trilite/libtrilite.so /usr/local/lib/libtrilite.so",
    }
}
