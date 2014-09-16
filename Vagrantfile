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

Vagrant::Config.run do |config|
    config.vm.box_url = "http://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
    config.vm.box = "ubuntu/trusty64"

    Vagrant.configure("1") do |config|
        config.vm.customize ["modifyvm", :id, "--memory", CONF['memory']]
        # Make sure guest additions are up to date!
        config.vbguest.auto_update = true
    end

    Vagrant.configure("2") do |config|
        config.vm.provider "virtualbox" do |v|
          v.name = "DXR_VM"
          v.customize ["modifyvm", :id, "--memory", CONF['memory']]
        end
    end

    is_jenkins = ENV['USER'] == 'jenkins'

    if not is_jenkins
        # Don't share these resources when on Jenkins. We want to be able to
        # parallelize jobs.

        # Add to /etc/hosts: 33.33.33.77 dxr
        config.vm.network :hostonly, "33.33.33.77"

        config.vm.forward_port 80, 8000
    end

    Vagrant.configure("1") do |config|
        # Enable symlinks, which trilite uses during build:
        config.vm.customize ["setextradata", :id,
            "VBoxInternal2/SharedFoldersEnableSymlinksCreate/vagrant-root", "1"]
    end

    Vagrant.configure("2") do |config|
        v.customize ["setextradata", :id,
            "VBoxInternal2/SharedFoldersEnableSymlinksCreate/vagrant-root", "1"]
    end

    if CONF['boot_mode'] == 'gui'
        config.vm.boot_mode = :gui
    end

    config.vm.share_folder("vagrant-root", MOUNT_POINT, ".")

    config.vm.provision "shell", path: "vagrant_provision.sh"
end
