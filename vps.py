import os
import paramiko
import time
import subprocess

from cloud_init_gen import CloudInitDoc

class VPS:
    
    def __init__(self, name, ram, cpu, ip, gateway, volume_group, disk_size, setup_env, setup_scripts, copy_files, result_files = {}):
        self.name = name
        self.ram = ram
        self.cpu = cpu
        self.ip = ip
        self.gateway = gateway
        self.volume_group = volume_group
        self.disk_size = disk_size
        self.setup_env = setup_env
        self.setup_scripts = setup_scripts
        self.copy_files = copy_files
        self.result_files = result_files        
        self.cloud_init_cdrom_iso = f"/var/lib/libvirt/images/user-data-{self.name}.iso"

    def create(self):
        self.create_cloudinit()
        self.install_os()
        self.check_ssh()
        self.setup()
        self.detach_cdrom()
        self.wait_for_ssh_to_be_ready()
        return self.get_return()
    
    def get_disk_path(self):
        return f'/dev/{self.volume_group}/{self.name}' 

    def create_cloudinit(self):
        """
        Vytvori Cloud Init ISO image
        """
        user_data = CloudInitDoc()
        user_data.add({
            'disable_root': False,
            'hostname': self.name,
            'password': '123456789', 
            'chpasswd': { 'expire': False }, 
            'ssh_pwauth': True,
            'ssh_deletekeys': False,
            'ssh_authorized_keys': ['ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCYKEBxWEQQEX+f04DQ7M6H/ltbWOWzP2jb274gGhDukqKoLqCisi7E15SO3zgBWDnNJ+7Zr5sFQaWr+t+aG8vCJQWJT9rykjy4BZhV6ZMGwvrMFw9/jLO1d+Habv4eFgeN8F/O8ijikE4v31uEp2//nJHOnrRX+YhFet4ON0fyWrGRnP1wYtyIQN1G7IgU/HBjKNsW8C8rO0keYlC3GwJOBEFnoVyZinqpCyOab8kM8gxIopRHBt6SseJANM2lBjOWpevboTmNXbvVMXuxCDugV+PDs4/RPBe9xBGWd0BXcN2G7Th47e1nLeWQQ3ztGR4O7RkvG7qs4F9nGPH0fyXZ'],
            'runcmd': [
                "userdel -r debian",
                "echo network: {config: disabled} > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg",
                "sed -i -e '/^#PermitRootLogin/s/^.*$/PermitRootLogin yes/' /etc/ssh/sshd_config"
            ],
            'manage_resolv_conf': False    
        })

        network_config = CloudInitDoc()
        network_config.add({
            'version': 1, 
            'config': [{
            'type': 'physical',
            'name': 'enp1s0',
            'subnets': [{
                'type' : 'static',
                'address' : self.ip + '/24',
                'gateway' : self.gateway,
            }],
            },
            {
            'type': 'nameserver',
            'interface': 'enp1s0',
            'address': [self.gateway]
            }]
        })

        userdatafile = f'user-data-{self.name}.yaml'
        with open(userdatafile, 'w') as file:
            file.write(user_data.render())

        networkfile = f'network-config-{self.name}.yaml'
        with open(networkfile, 'w') as file:
            file.write(network_config.render())    

        os.system(f'cloud-localds -N network-config-{self.name}.yaml {self.cloud_init_cdrom_iso} user-data-{self.name}.yaml')
        os.unlink(userdatafile)
        os.unlink(networkfile)
        return self.cloud_init_cdrom_iso

    def detach_cdrom(self):
        os.system(f"virsh shutdown {self.name}")
        error = True
        while error:
            error = os.system(f"virsh detach-disk --domain {self.name} {self.cloud_init_cdrom_iso} --persistent --config")
            time.sleep(2)
        os.system(f"virsh start {self.name}")
    
    def install_os(self, netinstall_image = '/root/debian-11-generic-amd64.raw'):
        os.system(f"dd if={netinstall_image} of={self.get_disk_path()} bs=4M")
        os.system(f"qemu-img resize {self.get_disk_path()} -f raw " + self.disk_size)
        os.system(f'virt-install --name {self.name} --disk path={self.get_disk_path()},device=disk,bus=virtio --disk {self.cloud_init_cdrom_iso},device=cdrom --os-variant debian10 --virt-type kvm --graphics none --vcpus "{str(round(self.cpu))}" --memory "{str(round(self.ram))}" -w bridge=br10 --console pty,target_type=serial --noautoconsole --import')

    def wait_for_ssh_to_be_ready(self, port = 22, timeout = 120, retry_interval = 1):
            client = paramiko.client.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                time.sleep(retry_interval)
                try:
                    client.connect(self.ip, int(port), allow_agent=False,look_for_keys=False)
                except paramiko.ssh_exception.SSHException as e:
                    break
                except paramiko.ssh_exception.NoValidConnectionsError as e:
                    print('SSH transport is not ready...')
                    continue
    
    def check_ssh(self):
        os.system(f'ssh-keygen -f "/root/.ssh/known_hosts" -R "{self.ip}"')
        self.wait_for_ssh_to_be_ready()
        os.system(f'ssh-keyscan -H {self.ip} >> ~/.ssh/known_hosts')

    def setup(self):
        env_export = ''
        for key in self.setup_env:
            env_export += key + "=" + str(self.setup_env[key]) + ' '
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username='root')        
        script_local_dir = '/mnt/doc'
        script_remote_tmpdir = '/root/tmpscript'

        if len(self.setup_scripts):
            ftp_client=ssh.open_sftp()
            for setup_scripts in self.setup_scripts:
                script = setup_scripts.split()[0]
                if len(setup_scripts.split()) > 1:        
                    args = setup_scripts.split()[1]
                else:
                    args = ''
                ftp_client.put(script_local_dir + script, script_remote_tmpdir)
                os.system(f'ssh {self.ip} chmod 777 {script_remote_tmpdir}')
                os.system(f'ssh {self.ip} {env_export} {script_remote_tmpdir} {args}')
            ftp_client.close()


        if len(self.copy_files):
            ftp_client=ssh.open_sftp()
            for copyscript in self.copy_files:
                script = copyscript.split(':')[0]
                dest = copyscript.split(':')[1]
                ftp_client.put(script_local_dir + script, dest)
            ftp_client.close()

        ssh.close()

    def get_return(self):
        r = {}
        for key in self.result_files:
            data = subprocess.run(f'ssh {self.ip} cat {self.result_files[key]}', capture_output=True, shell=True, text=True)
            r[key] = data.stdout.strip()
        return r