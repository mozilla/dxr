# Install python and compiled modules for project
class python ($project_path) {

    package {
        "python2.6-dev":
            ensure => installed,
            require => Exec['update-python-ppa'];

        "python2.6":
            ensure => installed,
            require => Exec['update-python-ppa'];

        #"libapache2-mod-wsgi":
            #ensure => installed,
            #require => "python2.6";

        "python-wsgi-intercept":
            ensure => installed,
            require => Exec['update-python-ppa'];

        "python-pip":
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

    #exec { "pip-install-development":
    #   cwd => ,
    #   command => "pip install -r $project_path/requirements/dev.txt",
    #   require => Package[$packages],
    #}

    #exec { "install-project":
    #   cwd => "$project_path",
    #   command => "pip install -r $project_path/requirements/dev.txt",
    #   require => Package[$packages],
    #}
}
