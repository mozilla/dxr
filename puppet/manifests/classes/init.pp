# Commands to run before all others in puppet.
class init {
    group { "puppet":
        ensure => "present",
    }

    case $operatingsystem {
        ubuntu: {
            exec { "update_apt":
                command => "sudo apt-get update",
            }

            # Provides "add-apt-repository" command, useful if you need
            # to install software from other apt repositories.
            package { ["python-software-properties", "build-essential"]:
                ensure => present,
                require => [
                    Exec['update_apt'],
                ];
            }
        }
    }
}
