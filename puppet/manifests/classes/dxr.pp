# dxr-specific commands that get dxr going so you don't have to

class dxr ($project_path){
    package {
         "libsqlite3-dev": ensure => installed;
         "git": ensure => installed;
         "mercurial": ensure => installed;
         "python-dev": ensure => installed;  # for MarkupSafe speedups
    }

    exec { "install-builddeps":
        command => "/usr/bin/sudo /usr/bin/apt-get -y build-dep firefox",
        timeout => 600,
    }

    exec { "install_llvm":
        command => "sudo /home/vagrant/install_llvm.sh",
        require => File["/home/vagrant/install_llvm.sh"],
        logoutput => "on_failure",
        timeout => 600,
    }

    # Install libtrilite so Apache WSGI processes can see it:
    file { "/usr/local/lib/libtrilite.so":
        ensure => "link",
        target => "/home/vagrant/dxr/trilite/libtrilite.so"
    }

    file { "/home/vagrant/install_llvm.sh":
        ensure => file,
        source => "$project_path/puppet/files/home/vagrant/install_llvm.sh",
        owner  => "vagrant", group => "vagrant", mode => 0755;
    }

    exec { "ldconfig":
        command => "/sbin/ldconfig",
        require => File["/usr/local/lib/libtrilite.so"]
    }
}
