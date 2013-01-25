# Install python and compiled modules for project
class python ($project_path) {

    $packages = ["libapache2-mod-wsgi",
                 "python2.6-dev",
                 "python2.6",
                 "python-pip"]

    package {
        $packages:
            ensure => installed,
            require => Exec['update-python-ppa'];
    }

    exec {
        "add-python-ppa":
            command => "/usr/bin/sudo add-apt-repository ppa:fkrull/deadsnakes",
            creates => "/etc/apt/sources.list.d/fkrull-deadsnakes-precise.list";

        "update-python-ppa":
            command => "/usr/bin/apt-get update && touch /tmp/update-python-ppa",
            require => Exec["add-python-ppa"],
            creates => "/tmp/update-python-ppa";
    }

    exec {
        "virtualenvwrapper":
            command => "pip install virtualenv virtualenvwrapper",
            require => Package["python-pip"];
    }


    exec {
       "pip-install-hglib":
           command => "pip install python-hglib",
           require => Package["python-pip"];
    }


    #exec { "pip-install-compiled":
    #
    #}

    exec {
        "pip-install-development":
            command => "pip install --no-deps -r $project_path/requirements.txt",
            require => Package[$packages],
    }

    exec {
        "dxr-setup-develop":
            cwd => "$project_path",
            # TODO: Change this to python2.6 once we get pip using 2.6:
            command => "python setup.py develop",
            require => Exec["pip-install-development"],
    }

    #exec { "install-project":
    #   cwd => "$project_path",
    #   command => "pip install -r $project_path/requirements/dev.txt",
    #   require => Package[$packages],
    #}
}
