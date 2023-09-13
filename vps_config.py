import yaml

class NetworkConfig:
    def __init__(self, ip, gateway = "10.0.0.1"):
        self.ip = ip
        self.gateway = gateway

class DiskConfig:
    def __init__(self, size = "10G", volume_group = "vg0"):
        self.volume_group = volume_group
        self.size = size

class SetupConfig:
    def __init__(self, scripts = [], playbook = None, files = [], env = {}, artifacts = {}):
        self.env = env
        self.scripts = scripts
        self.playbook = playbook
        self.files = files
        self.artifacts = artifacts
        

class ServerConfig:
    def __init__(self, hostname, network:NetworkConfig, disk:DiskConfig = DiskConfig(), setup:SetupConfig = None, ram = 1024, cpu = 2):
        self.hostname = hostname
        self.ram = ram
        self.cpu = cpu
        self.network = network
        self.disk = disk
        self.setup = SetupConfig() if setup is None else setup

    @classmethod
    def from_yaml(cls, yaml_file):
        with open(yaml_file, 'r') as file:
            data = yaml.safe_load(file)
        
        network_data = data.get('network', {})
        network = NetworkConfig(
            ip=network_data.get('ip'),
            gateway=network_data.get('gateway')
        )
        
        disk_data = data.get('disk', {})
        disk = DiskConfig(
            volume_group=disk_data.get('volume_group'),
            size=disk_data.get('size')
        )
        
        setup_data = data.get('setup', {})
        setup = SetupConfig(
            playbooks=setup_data.get('playbooks', []),
            scripts=setup_data.get('scripts', []),
            files=setup_data.get('files', []),
            env=setup_data.get('env', {}),
            artifacts=setup_data.get('artifacts', {})
        )
        
        return cls(
            hostname=data.get('hostname'),
            ram=data.get('ram'),
            cpu=data.get('cpu'),
            network=network,
            disk=disk,
            setup=setup
        )

    def __str__(self):
        return yaml.dump(self.__dict__, default_flow_style=False)