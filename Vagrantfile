require "yaml"

# Load up our vagrant config files -- vagrantconfig.yaml first
_config = YAML.load(File.open(File.join(File.dirname(__FILE__),
                    "vagrantconfig.yaml"), File::RDONLY).read)

# Local-specific/not-git-managed config -- vagrantconfig_local.yaml
begin
    _config.merge!(YAML.load(File.open(File.join(File.dirname(__FILE__),
                   "vagrantconfig_local.yaml"), File::RDONLY).read))
rescue Errno::ENOENT # No vagrantconfig_local.yaml found -- that's OK; just
                     # use the defaults.
end

CONF = _config
MOUNT_POINT = '/home/vagrant/dxr'


Vagrant::Config.run do |config|
    config.vm.box = "precise64"
    config.vm.box_url = "http://files.vagrantup.com/precise64.box"

    Vagrant.configure("1") do |config|
        config.vm.customize ["modifyvm", :id, "--memory", CONF['memory']]
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

    config.vm.provision :puppet do |puppet|
        puppet.manifests_path = "puppet/manifests"
        puppet.manifest_file = "init.pp"
        # enable this to see verbose and debug puppet output
        if CONF['debug_mode'] == true
            puppet.options = "--verbose --debug"
        end
    end
end
