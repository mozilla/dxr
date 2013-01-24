# dxr-specific commands that get dxr going so you don't have to

class dxr ($project_path){
    package {
         "python-jinja2": ensure => installed;
         "python-pygments": ensure => installed;
         "libsqlite3-dev": ensure => installed;
         "libclang-dev": ensure => installed;
         "clang": ensure => installed;
         "git": ensure => installed;
         "mercurial": ensure => installed;
         "llvm-dev": ensure => installed;
    }

    exec { "install-builddeps":
        command => "/usr/bin/sudo /usr/bin/apt-get -y build-dep firefox";
    }

    exec { "use-llvm-3":
        command => "sudo cp /usr/bin/llvm-config-3.0 /usr/bin/llvm-config",
        require => [Package["llvm-dev"], Package["libclang-dev"], Package["clang"]],
        logoutput => "on_failure",
    }
}
