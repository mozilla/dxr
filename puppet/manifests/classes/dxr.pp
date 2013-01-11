# dxr-specific commands that get dxr going so you don't have to

class dxr ($project_path){
    package {
         "python-jinja2": ensure => installed;
         "python-pygments": ensure => installed;
         "libsqlite3-dev": ensure => installed;
         "git": ensure => installed;
         "mercurial": ensure => installed;
    }

    exec { "install-builddeps":
        command => "/usr/bin/sudo /usr/bin/apt-get -y build-dep firefox";
    }

    exec { "install_llvm":
        command => "sudo /home/vagrant/install_llvm.sh",
        require => File["/home/vagrant/install_llvm.sh"],
        logoutput => "on_failure",
    }

    file { "/home/vagrant/.bashrc_vagrant":
        ensure => file,
        source => "$project_path/puppet/files/home/vagrant/bashrc_vagrant",
        owner  => "vagrant", group => "vagrant", mode => 0644;
    }

    file { "/home/vagrant/install_llvm.sh":
        ensure => file,
        source => "$project_path/puppet/files/home/vagrant/install_llvm.sh",
        owner  => "vagrant", group => "vagrant", mode => 0755;
    }

    exec { "amend_rc":
        command => "echo 'if [ -f /home/vagrant/.bashrc_vagrant ] && ! shopt -oq posix; then . /home/vagrant/.bashrc_vagrant; fi' >> /home/vagrant/.bashrc",
        require => File["/home/vagrant/.bashrc_vagrant"],
    }

}
