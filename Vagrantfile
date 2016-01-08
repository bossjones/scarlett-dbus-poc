Vagrant.configure("2")  do |config|

  # base information
  config.vm.box = "scarlettpi-base-ubuntu-14-04-pulse"
  config.vm.box_url = "/Users/malcolm/ubuntu_14_04_base_w_gst_pulseaudio_guestadd3.box"

  # name
  # CHANGME
  config.vm.hostname = "scarlettpi-system7"
  config.vm.boot_timeout = 400
  config.vm.box_version = "0.1.0"

  # networking
  config.vm.network "public_network", :bridge => 'en0: Wi-Fi (AirPort)'
  config.vm.network "forwarded_port", guest: 19360, host: 1936
  config.vm.network "forwarded_port", guest: 139, host: 1139
  config.vm.network "forwarded_port", guest: 8081, host: 8881
  config.vm.network "forwarded_port", guest: 2376, host: 2376

  config.ssh.username = "pi"
  config.ssh.host = "127.0.0.1"
  config.ssh.guest_port = "2222"
  config.ssh.private_key_path = "/Users/malcolm/.ssh/id_rsa_ssh"
  config.ssh.forward_agent = true
  config.ssh.forward_x11 = true
  #config.ssh.pty = true
  config.ssh.shell = "bash -c 'BASH_ENV=/etc/profile exec bash'"

  # config.vm.provision "shell", path: "./bootstrap/start_anaconda.sh"

  config.vm.provider :virtualbox do |vb|
    # Don't boot with headless mode
    vb.gui = true

    # user modifiable memory/cpu settings
    vb.memory = 2048
    vb.cpus = 2

    # use host dns resolver
    # vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
  end

end
