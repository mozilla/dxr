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
    config.vm.box = "saucy64"
    config.vm.box_url = "http://cloud-images.ubuntu.com/vagrant/saucy/current/saucy-server-cloudimg-amd64-vagrant-disk1.box"
    config.vm.customize ["modifyvm", :id, "--memory", 1024]

    is_jenkins = ENV['USER'] == 'jenkins'

    if not is_jenkins
        # Don't share these resources when on Jenkins. We want to be able to
        # parallelize jobs.

        # Add to /etc/hosts: 33.33.33.77 dxr
        config.vm.network :hostonly, "33.33.33.77"

        config.vm.forward_port 80, 8000
    end

    # Enable symlinks, which trilite uses during build:
    config.vm.customize ["setextradata", :id, "VBoxInternal2/SharedFoldersEnableSymlinksCreate/vagrant-root", "1"]

    if CONF['boot_mode'] == 'gui'
        config.vm.boot_mode = :gui
    end

    config.vm.share_folder("vagrant-root", MOUNT_POINT, ".")

    config.vm.provision "shell", path: "vagrant_provision.sh"
end
