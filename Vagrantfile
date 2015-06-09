require "yaml"

# Load up our vagrant config files -- vagrantconfig.yaml first
_config = YAML.load(File.open(File.join(File.dirname(__FILE__),
                    "vagrantconfig.yaml"), File::RDONLY).read)

# Local-specific/not-git-managed config -- vagrantconfig_local.yaml
begin
    extra = YAML.load(File.open(File.join(File.dirname(__FILE__),
                      "vagrantconfig_local.yaml"), File::RDONLY).read)
    if extra
        _config.merge!(extra)
    end
rescue Errno::ENOENT # No vagrantconfig_local.yaml found -- that's OK; just
                     # use the defaults.
end

CONF = _config
MOUNT_POINT = '/home/vagrant/dxr'

Vagrant.configure("2") do |config|
    config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
    config.vm.box = "ubuntu/trusty64"

    is_jenkins = ENV['USER'] == 'jenkins'

    config.vm.provider "virtualbox" do |v|
        # On Jenkins, choose a unique box name so test runs don't collide if
        # they get assigned to the same worker:
        v.name = is_jenkins ? ("DXR_VM_" + ENV['JOB_NAME'] + "_" + ENV['BUILD_NUMBER']) : "DXR_VM"

        v.customize ["modifyvm", :id, "--memory", CONF['memory']]
        v.customize ["setextradata", :id,
            "VBoxInternal2/SharedFoldersEnableSymlinksCreate//home/vagrant/dxr", "1"]
    end

    if not is_jenkins
        # Don't share these resources when on Jenkins. We want to be able to
        # parallelize jobs.

        # Add to /etc/hosts: 33.33.33.77 dxr
        config.vm.network "private_network", ip: "33.33.33.77"
        config.vm.network "forwarded_port", guest: 80, host: 8000
    end

    if CONF['boot_mode'] == 'gui'
        config.vm.boot_mode = :gui
    end

    config.vm.synced_folder ".", MOUNT_POINT

    config.vm.provision "shell", path: "vagrant_provision.sh"
end
