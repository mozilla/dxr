# Install python and compiled modules for project
class python ($project_path) {

    $packages = ["libapache2-mod-wsgi",
                 "python-pip"]

    package {
        $packages:
            ensure => installed;
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

    exec {
        "nose":
            command => "pip install nose",
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
            command => "python setup.py develop",
            require => Exec["pip-install-development"],
    }

    #exec { "install-project":
    #   cwd => "$project_path",
    #   command => "pip install -r $project_path/requirements/dev.txt",
    #   require => Package[$packages],
    #}
}
