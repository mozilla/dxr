# Commands to run before all others in puppet.
class init {

    exec { "update_apt":
        command => "sudo apt-get update",
    }

    # Provides "add-apt-repository" command, useful if you need
    # to install software from other apt repositories.
    package { ["python-software-properties", "build-essential"]:
        ensure => present,
        require => Exec['update_apt']
    }

    # provide all the build tools and environment for testing the VM
    package { ["npm",
               "libapache2-mod-wsgi",
               "python-pip",
               "apache2-dev",
               "apache2",
               "libsqlite3-dev",
               "git",
               "mercurial",
               "llvm-3.3", 
               "libclang-3.3-dev",
               "clang-3.3",
               "pkg-config"]:
        ensure => present,
        require => Exec['update_apt']
    }

}