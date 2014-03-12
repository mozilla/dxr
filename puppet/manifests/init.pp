# Just include a basic init module to install required packages
# Do this in puppet instead of in the VM to ensure apt-get doesn't
# run out of memory when run inside the VM in Jenkins

# set $PATH so any module doesn't have to
Exec {
    path => "/usr/local/bin:/usr/bin:/usr/sbin:/sbin:/bin",
    logoutput => "on_failure"
}

include init