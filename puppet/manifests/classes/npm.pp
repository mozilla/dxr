# Install node and npm.
class npm {
    package { "npm":
        ensure => present;
    }
}
