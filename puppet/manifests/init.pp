import "classes/*.pp"

$PROJ_DIR = "/home/vagrant/dxr"

#$DB_NAME = "dxr"
#$DB_USER = "root"

Exec {
    path => "/usr/local/bin:/usr/bin:/usr/sbin:/sbin:/bin",
    logoutput => "on_failure"
}

class dev {
    class {
        init: ;
    }
    class { "python":
        require => Class[init],
        project_path => $PROJ_DIR;
    }
    class { "apache":
        require => Class[python];
    }
    class { "dxr":
        require => Class[apache],
        project_path => $PROJ_DIR;
    }
}

include dev
